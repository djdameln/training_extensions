"""Task of OTX Classification using mmclassification training backend."""

# Copyright (C) 2023 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import glob
import os
import time
from contextlib import nullcontext
from copy import deepcopy
from functools import partial
from typing import Any, Dict, Optional, Type, Union

import torch
from mmcls.apis import train_model
from mmcls.datasets import build_dataloader, build_dataset
from mmcls.models.backbones.vision_transformer import VisionTransformer
from mmcls.utils import collect_env
from mmcv.runner import wrap_fp16_model
from mmcv.utils import Config, ConfigDict

from otx.algorithms.classification.adapters.mmcls.utils.exporter import (
    ClassificationExporter,
)
from otx.algorithms.classification.task import OTXClassificationTask
from otx.algorithms.common.adapters.mmcv.hooks import LossDynamicsTrackingHook
from otx.algorithms.common.adapters.mmcv.hooks.recording_forward_hook import (
    ActivationMapHook,
    BaseRecordingForwardHook,
    EigenCamHook,
    FeatureVectorHook,
    ReciproCAMHook,
    ViTFeatureVectorHook,
    ViTReciproCAMHook,
)
from otx.algorithms.common.adapters.mmcv.utils import (
    adapt_batch_size,
    build_data_parallel,
    get_configs_by_pairs,
)
from otx.algorithms.common.adapters.mmcv.utils import (
    build_dataloader as otx_build_dataloader,
)
from otx.algorithms.common.adapters.mmcv.utils import (
    build_dataset as otx_build_dataset,
)
from otx.algorithms.common.adapters.mmcv.utils.config_utils import (
    InputSizeManager,
    OTXConfig,
)
from otx.algorithms.common.adapters.torch.utils import convert_sync_batchnorm
from otx.algorithms.common.configs.configuration_enums import BatchSizeAdaptType
from otx.algorithms.common.configs.training_base import TrainType
from otx.algorithms.common.tasks.nncf_task import NNCFBaseTask
from otx.algorithms.common.utils.data import get_dataset
from otx.api.entities.datasets import DatasetEntity
from otx.api.entities.explain_parameters import ExplainParameters
from otx.api.entities.inference_parameters import InferenceParameters
from otx.api.entities.model import ModelPrecision
from otx.api.entities.subset import Subset
from otx.api.entities.task_environment import TaskEnvironment
from otx.api.usecases.tasks.interfaces.export_interface import ExportType
from otx.utils.logger import get_logger

from .configurer import (
    ClassificationConfigurer,
    IncrClassificationConfigurer,
    SemiSLClassificationConfigurer,
)
from .utils import build_classifier

logger = get_logger()

# TODO Remove unnecessary pylint disable
# pylint: disable=too-many-lines


class MMClassificationTask(OTXClassificationTask):
    """Task class for OTX classification using mmclassification training backend."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, task_environment: TaskEnvironment, output_path: Optional[str] = None):
        super().__init__(task_environment, output_path)
        self._data_cfg: Optional[Config] = None
        self._recipe_cfg: Optional[Config] = None

    # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    def _init_task(self):  # noqa
        """Initialize task."""

        if self._multilabel:
            cfg_path = os.path.join(self._model_dir, "model_multilabel.py")
        elif self._hierarchical:
            cfg_path = os.path.join(self._model_dir, "model_hierarchical.py")
        else:
            cfg_path = os.path.join(self._model_dir, "model.py")
        self._recipe_cfg = OTXConfig.fromfile(cfg_path)
        self._recipe_cfg.domain = self._task_type.domain
        self._recipe_cfg.model.multilabel = self._multilabel
        self._recipe_cfg.model.hierarchical = self._hierarchical
        if self._hierarchical:
            self._recipe_cfg.model.head.hierarchical_info = self._hierarchical_info
        self._config = self._recipe_cfg

        self.set_seed()

        # Loss dynamics tracking
        if getattr(self._hyperparams.algo_backend, "enable_noisy_label_detection", False):
            LossDynamicsTrackingHook.configure_recipe(self._recipe_cfg, self._output_path)

    # pylint: disable=too-many-arguments
    def configure(
        self,
        training=True,
        ir_options=None,
        export=False,
    ):
        """Patch mmcv configs for OTX classification settings."""

        # deepcopy all configs to make sure
        # changes under Configurer and below does not take an effect to OTX for clear distinction
        recipe_cfg = deepcopy(self._recipe_cfg)
        assert recipe_cfg is not None, "'recipe_cfg' is not initialized."

        if self._data_cfg is not None:
            data_classes = [label.name for label in self._labels]
        else:
            data_classes = None
        model_classes = [label.name for label in self._model_label_schema]

        recipe_cfg.work_dir = self._output_path
        recipe_cfg.resume = self._resume

        if self._train_type == TrainType.Incremental:
            configurer = IncrClassificationConfigurer(
                "classification",
                training,
                export,
                self.override_configs,
                self.on_hook_initialized,
                self._time_monitor,
                self._learning_curves,
            )
        elif self._train_type == TrainType.Semisupervised:
            configurer = SemiSLClassificationConfigurer(
                "classification",
                training,
                export,
                self.override_configs,
                self.on_hook_initialized,
                self._time_monitor,
                self._learning_curves,
            )
        else:
            configurer = ClassificationConfigurer(
                "classification",
                training,
                export,
                self.override_configs,
                self.on_hook_initialized,
                self._time_monitor,
                self._learning_curves,
            )

        options_for_patch_datasets = {"type": "OTXClsDataset", "empty_label": self._empty_label}
        options_for_patch_evaluation = {"task": "normal"}
        if self._multilabel:
            options_for_patch_datasets["type"] = "OTXMultilabelClsDataset"
            options_for_patch_evaluation["task"] = "multilabel"
        elif self._hierarchical:
            options_for_patch_datasets["type"] = "OTXHierarchicalClsDataset"
            options_for_patch_datasets["hierarchical_info"] = self._hierarchical_info
            options_for_patch_datasets["label_schema"] = self._task_environment.label_schema
            options_for_patch_evaluation["task"] = "hierarchical"
        elif self._selfsl:
            options_for_patch_datasets["type"] = "SelfSLDataset"

        cfg = configurer.configure(
            recipe_cfg,
            self.data_pipeline_path,
            self._hyperparams,
            self._model_ckpt,
            self._data_cfg,
            ir_options,
            data_classes,
            model_classes,
            self._input_size,
            options_for_patch_datasets=options_for_patch_datasets,
            options_for_patch_evaluation=options_for_patch_evaluation,
        )
        self._config = cfg
        self._input_size = cfg.model.pop("input_size", None)
        return cfg

    def build_model(
        self,
        cfg: Config,
        fp16: bool = False,
        **kwargs,
    ) -> torch.nn.Module:
        """Build model from model_builder."""
        model_builder = getattr(self, "model_builder", build_classifier)
        model = model_builder(cfg, **kwargs)
        if bool(fp16):
            wrap_fp16_model(model)
        if bool(cfg.get("channel_last", False)):
            model = model.to(memory_format=torch.channels_last)
        return model

    def _infer_model(
        self,
        dataset: DatasetEntity,
        inference_parameters: Optional[InferenceParameters] = None,
    ):
        """Main infer function."""
        self._data_cfg = ConfigDict(
            data=ConfigDict(
                train=ConfigDict(
                    otx_dataset=None,
                    labels=self._labels,
                ),
                test=ConfigDict(
                    otx_dataset=dataset,
                    labels=self._labels,
                ),
            )
        )

        dump_saliency_map = not inference_parameters.is_evaluation if inference_parameters else True

        self._init_task()

        cfg = self.configure(False, None)
        logger.info("infer!")

        # Data loader
        mm_dataset = build_dataset(cfg.data.test)
        workers_per_gpu = cfg.data.test_dataloader.get("workers_per_gpu", 0)
        dataloader = build_dataloader(
            mm_dataset,
            samples_per_gpu=cfg.data.test_dataloader.get("samples_per_gpu", 1),
            workers_per_gpu=workers_per_gpu,
            num_gpus=len(cfg.gpu_ids),
            dist=cfg.distributed,
            seed=cfg.get("seed", None),
            shuffle=False,
            persistent_workers=(workers_per_gpu > 0),
        )

        # Model
        model = self.build_model(cfg, fp16=cfg.get("fp16", False))

        model.eval()
        feature_model = model
        model = build_data_parallel(model, cfg, distributed=False)

        # InferenceProgressCallback (Time Monitor enable into Infer task)
        time_monitor = None
        if cfg.get("custom_hooks", None):
            time_monitor = [hook.time_monitor for hook in cfg.custom_hooks if hook.type == "OTXProgressHook"]
            time_monitor = time_monitor[0] if time_monitor else None
        if time_monitor is not None:
            # pylint: disable=unused-argument
            def pre_hook(module, inp):
                time_monitor.on_test_batch_begin(None, None)

            def hook(module, inp, outp):
                time_monitor.on_test_batch_end(None, None)

            model.register_forward_pre_hook(pre_hook)
            model.register_forward_hook(hook)

        model_type = cfg.model.backbone.type.split(".")[-1]  # mmcls.VisionTransformer => VisionTransformer
        forward_explainer_hook: Union[nullcontext, BaseRecordingForwardHook]
        if model_type == "VisionTransformer":
            forward_explainer_hook = ViTReciproCAMHook(feature_model)
        elif not dump_saliency_map:
            forward_explainer_hook = nullcontext()
        else:
            forward_explainer_hook = ReciproCAMHook(feature_model)

        feature_vector_hook: Union[nullcontext, BaseRecordingForwardHook]
        if model_type == "VisionTransformer":
            feature_vector_hook = ViTFeatureVectorHook(feature_model)
        elif not dump_saliency_map:
            feature_vector_hook = nullcontext()
        else:
            feature_vector_hook = FeatureVectorHook(feature_model)

        eval_predictions = []
        feature_vectors = []
        saliency_maps = []

        with feature_vector_hook:
            with forward_explainer_hook:
                for data in dataloader:
                    with torch.no_grad():
                        result = model(return_loss=False, **data)
                    eval_predictions.extend(result)
                if isinstance(feature_vector_hook, nullcontext):
                    feature_vectors = [None] * len(mm_dataset)
                else:
                    feature_vectors = feature_vector_hook.records  # pylint: disable=no-member
                if isinstance(forward_explainer_hook, nullcontext):
                    saliency_maps = [None] * len(mm_dataset)
                else:
                    saliency_maps = forward_explainer_hook.records  # pylint: disable=no-member
                if len(eval_predictions) == 0:
                    eval_predictions = [None] * len(mm_dataset)

        assert len(eval_predictions) == len(feature_vectors) == len(saliency_maps), (
            "Number of elements should be the same, however, number of outputs are "
            f"{len(eval_predictions)}, {len(feature_vectors)}, and {len(saliency_maps)}"
        )

        outputs = dict(
            eval_predictions=eval_predictions,
            feature_vectors=feature_vectors,
            saliency_maps=saliency_maps,
        )
        return outputs

    # pylint: disable=too-many-branches, too-many-statements
    def _train_model(
        self,
        dataset: DatasetEntity,
    ):
        """Train function in MMClassificationTask."""
        self._data_cfg = ConfigDict(data=ConfigDict())

        for cfg_key, subset in zip(
            ["train", "val", "unlabeled"],
            [Subset.TRAINING, Subset.VALIDATION, Subset.UNLABELED],
        ):
            subset = get_dataset(dataset, subset)
            if subset and self._data_cfg is not None:
                self._data_cfg.data[cfg_key] = ConfigDict(
                    otx_dataset=subset,
                    labels=self._labels,
                )

        self._is_training = True

        self._init_task()

        cfg = self.configure(True, None)
        logger.info("train!")

        timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())

        # Environment
        logger.info(f"cfg.gpu_ids = {cfg.gpu_ids}, distributed = {cfg.distributed}")
        env_info_dict = collect_env()
        env_info = "\n".join([(f"{k}: {v}") for k, v in env_info_dict.items()])
        dash_line = "-" * 60 + "\n"
        logger.info(f"Environment info:\n{dash_line}{env_info}\n{dash_line}")

        # Data
        datasets = [build_dataset(cfg.data.train)]

        # Metadata
        meta = dict()
        meta["env_info"] = env_info
        meta["seed"] = cfg.get("seed", 5)
        meta["exp_name"] = cfg.work_dir

        # Model
        model = self.build_model(cfg, fp16=cfg.get("fp16", False))
        if not torch.cuda.is_available():
            # NOTE: mmcls does not wrap models w/ DP for CPU training not like mmdet
            # Raw DataContainer "img_metas" is exposed, which results in errors
            model = build_data_parallel(model, cfg, distributed=False)
        model.train()

        if cfg.distributed:
            convert_sync_batchnorm(model)

        validate = bool(cfg.data.get("val", None))
        if validate:
            val_dataset = build_dataset(cfg.data.val, dict(test_mode=True))
            val_loader_cfg = Config(
                cfg_dict={
                    "num_gpus": len(cfg.gpu_ids),
                    "dist": cfg.distributed,
                    "round_up": True,
                    "seed": cfg.seed,
                    "shuffle": False,  # Not shuffle by default
                    "sampler_cfg": None,  # Not use sampler by default
                    **cfg.data.get("val_dataloader", {}),
                }
            )
            val_dataloader = build_dataloader(val_dataset, **val_loader_cfg)
            eval_cfg = cfg.get("evaluation", {})
            eval_cfg["by_epoch"] = cfg.runner["type"] != "IterBasedRunner"
            cfg.custom_hooks.append(
                dict(
                    type="DistCustomEvalHook" if cfg.distributed else "CustomEvalHook",
                    dataloader=val_dataloader,
                    priority="ABOVE_NORMAL",
                    **eval_cfg,
                )
            )

        if self._hyperparams.learning_parameters.auto_adapt_batch_size != BatchSizeAdaptType.NONE:
            train_func = partial(train_model, meta=deepcopy(meta), model=deepcopy(model), distributed=False)
            adapt_batch_size(
                train_func,
                cfg,
                datasets,
                isinstance(self, NNCFBaseTask),  # nncf needs eval hooks
                not_increase=(self._hyperparams.learning_parameters.auto_adapt_batch_size == BatchSizeAdaptType.SAFE),
            )

        train_model(
            model,
            datasets,
            cfg,
            distributed=cfg.distributed,
            validate=False,  # For using CustomEvalHook
            timestamp=timestamp,
            meta=meta,
        )

        # Save outputs
        output_ckpt_path = os.path.join(cfg.work_dir, "latest.pth")
        best_ckpt_path = glob.glob(os.path.join(cfg.work_dir, "best_*.pth"))
        if len(best_ckpt_path) > 0:
            output_ckpt_path = best_ckpt_path[0]
        return dict(
            final_ckpt=output_ckpt_path,
        )

    def _explain_model(self, dataset: DatasetEntity, explain_parameters: Optional[ExplainParameters]):
        """Explain function in MMClassificationTask."""
        self._data_cfg = ConfigDict(
            data=ConfigDict(
                train=ConfigDict(
                    otx_dataset=None,
                    labels=self._labels,
                ),
                test=ConfigDict(
                    otx_dataset=dataset,
                    labels=self._labels,
                ),
            )
        )

        self._init_task()
        cfg = self.configure(False, None)
        # Data loader
        mm_dataset = otx_build_dataset(cfg, "test", build_dataset)
        dataloader = otx_build_dataloader(
            mm_dataset,
            cfg,
            "test",
            build_dataloader,
            distributed=False,
            round_up=False,
        )
        model = self.build_model(cfg, fp16=cfg.get("fp16", False))
        model.eval()
        feature_model = model
        model = build_data_parallel(model, cfg, distributed=False)

        # InferenceProgressCallback (Time Monitor enable into Infer task)
        time_monitor = None
        if cfg.get("custom_hooks", None):
            time_monitor = [hook.time_monitor for hook in cfg.custom_hooks if hook.type == "OTXProgressHook"]
            time_monitor = time_monitor[0] if time_monitor else None
        if time_monitor is not None:

            def pre_hook(module, inp):  # pylint: disable=unused-argument
                time_monitor.on_test_batch_begin(None, None)

            def hook(module, inp, outp):  # pylint: disable=unused-argument
                time_monitor.on_test_batch_end(None, None)

            model.register_forward_pre_hook(pre_hook)
            model.register_forward_hook(hook)

        per_class_xai_algorithm: Union[Type[ViTReciproCAMHook], Type[ReciproCAMHook]]
        if isinstance(model.module.backbone, VisionTransformer):
            per_class_xai_algorithm = ViTReciproCAMHook
        else:
            per_class_xai_algorithm = ReciproCAMHook
        explainer_hook_selector = {
            "eigencam": EigenCamHook,
            "activationmap": ActivationMapHook,
            "classwisesaliencymap": per_class_xai_algorithm,
        }
        explainer = explain_parameters.explainer if explain_parameters else None
        if explainer is not None:
            explainer_hook = explainer_hook_selector.get(explainer.lower())
        else:
            explainer_hook = None
        if explainer_hook is None:
            raise NotImplementedError("Explainer algorithm not supported!")

        eval_predictions = []
        with explainer_hook(feature_model) as forward_explainer_hook:
            # do inference and record intermediate fmap
            for data in dataloader:
                with torch.no_grad():
                    result = model(return_loss=False, **data)
                eval_predictions.extend(result)
            saliency_maps = forward_explainer_hook.records

        assert len(eval_predictions) == len(saliency_maps), (
            "Number of elements should be the same, however, number of outputs are "
            f"{len(eval_predictions)}, and {len(saliency_maps)}"
        )

        return eval_predictions, saliency_maps

    def _export_model(self, precision: ModelPrecision, export_format: ExportType, dump_features: bool):
        self._data_cfg = ConfigDict(
            data=ConfigDict(
                train=ConfigDict(
                    otx_dataset=None,
                    labels=self._labels,
                ),
                test=ConfigDict(
                    otx_dataset=None,
                    labels=self._labels,
                ),
            )
        )
        self._init_task()

        cfg = self.configure(False, None, export=True)

        self._precision[0] = precision
        assert len(self._precision) == 1
        export_options: Dict[str, Any] = {}
        export_options["deploy_cfg"] = self._init_deploy_cfg(cfg)

        export_options["precision"] = str(precision)
        export_options["type"] = str(export_format)

        export_options["deploy_cfg"]["dump_features"] = dump_features
        if dump_features:
            output_names = export_options["deploy_cfg"]["ir_config"]["output_names"]
            if "feature_vector" not in output_names:
                output_names.append("feature_vector")
            if export_options["deploy_cfg"]["codebase_config"]["task"] != "Segmentation":
                if "saliency_map" not in output_names:
                    output_names.append("saliency_map")
        export_options["model_builder"] = getattr(self, "model_builder", build_classifier)

        if precision == ModelPrecision.FP16:
            export_options["deploy_cfg"]["backend_config"]["mo_options"]["flags"].append("--compress_to_fp16")

        backend_cfg_backup = {}
        if export_format == ExportType.ONNX:
            backend_cfg_backup = export_options["deploy_cfg"]["backend_config"]
            export_options["deploy_cfg"]["backend_config"] = {"type": "onnxruntime"}
            export_options["deploy_cfg"]["ir_config"]["dynamic_axes"]["data"] = {0: "batch"}

        exporter = ClassificationExporter()
        results = exporter.run(
            cfg,
            **export_options,
        )

        if export_format == ExportType.ONNX:
            results["inference_parameters"] = {}
            results["inference_parameters"]["mean_values"] = " ".join(
                map(str, backend_cfg_backup["mo_options"]["args"]["--mean_values"])
            )
            results["inference_parameters"]["scale_values"] = " ".join(
                map(str, backend_cfg_backup["mo_options"]["args"]["--scale_values"])
            )

        return results

    def _init_deploy_cfg(self, cfg: Config) -> Union[Config, None]:
        base_dir = os.path.abspath(os.path.dirname(self._task_environment.model_template.model_template_path))
        deploy_cfg_path = os.path.join(base_dir, "deployment.py")
        deploy_cfg = None
        if os.path.exists(deploy_cfg_path):
            deploy_cfg = OTXConfig.fromfile(deploy_cfg_path)

            def patch_input_preprocessing(deploy_cfg):
                normalize_cfg = get_configs_by_pairs(
                    cfg.data.test.pipeline,
                    dict(type="Normalize"),
                )
                assert len(normalize_cfg) == 1
                normalize_cfg = normalize_cfg[0]

                options = dict(flags=[], args={})
                # NOTE: OTX loads image in RGB format
                # so that `to_rgb=True` means a format change to BGR instead.
                # Conventionally, OpenVINO IR expects a image in BGR format
                # but OpenVINO IR under OTX assumes a image in RGB format.
                #
                # `to_rgb=True` -> a model was trained with images in BGR format
                #                  and a OpenVINO IR needs to reverse input format from RGB to BGR
                # `to_rgb=False` -> a model was trained with images in RGB format
                #                   and a OpenVINO IR does not need to do a reverse
                if normalize_cfg.get("to_rgb", False):
                    options["flags"] += ["--reverse_input_channels"]
                # value must be a list not a tuple
                if normalize_cfg.get("mean", None) is not None:
                    options["args"]["--mean_values"] = list(normalize_cfg.get("mean"))
                if normalize_cfg.get("std", None) is not None:
                    options["args"]["--scale_values"] = list(normalize_cfg.get("std"))

                # fill default
                backend_config = deploy_cfg.backend_config
                if backend_config.get("mo_options") is None:
                    backend_config.mo_options = ConfigDict()
                mo_options = backend_config.mo_options
                if mo_options.get("args") is None:
                    mo_options.args = ConfigDict()
                if mo_options.get("flags") is None:
                    mo_options.flags = []

                # already defiend options have higher priority
                options["args"].update(mo_options.args)
                mo_options.args = ConfigDict(options["args"])
                # make sure no duplicates
                mo_options.flags.extend(options["flags"])
                mo_options.flags = list(set(mo_options.flags))

            def patch_input_shape(deploy_cfg):
                input_size_manager = InputSizeManager(cfg)
                size = input_size_manager.get_input_size_from_cfg("test")
                assert all(isinstance(i, int) and i > 0 for i in size)
                # default is static shape to prevent an unexpected error
                # when converting to OpenVINO IR
                deploy_cfg.backend_config.model_inputs = [ConfigDict(opt_shapes=ConfigDict(input=[1, 3, *size]))]

            patch_input_preprocessing(deploy_cfg)
            patch_input_shape(deploy_cfg)

        return deploy_cfg

    # This should be removed
    def update_override_configurations(self, config):
        """Update override_configs."""
        logger.info(f"update override config with: {config}")
        config = ConfigDict(**config)
        self.override_configs.update(config)
