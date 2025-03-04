"""Tests for Action Classification Task with OTX CLI"""
# Copyright (C) 2022 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import os
import copy
from copy import deepcopy

import pytest
import torch

from otx.api.entities.model_template import parse_model_template
from otx.cli.registry import Registry
from tests.test_suite.e2e_test_system import e2e_pytest_component
from tests.test_suite.run_test_command import (
    otx_eval_openvino_testing,
    otx_eval_testing,
    otx_export_testing,
    otx_train_testing,
    otx_resume_testing,
    get_template_dir,
)

# Finetuning arguments
# TODO: Need to change sample dataset
args = {
    "--train-data-roots": "tests/assets/cvat_dataset/action_classification/train",
    "--val-data-roots": "tests/assets/cvat_dataset/action_classification/train",
    "--test-data-roots": "tests/assets/cvat_dataset/action_classification/train",
    "train_params": ["params", "--learning_parameters.num_iters", "1", "--learning_parameters.batch_size", "4"],
}

# Training params for resume, num_iters*2
resume_params = [
    "params",
    "--learning_parameters.num_iters",
    "2",
    "--learning_parameters.batch_size",
    "4",
]

otx_dir = os.getcwd()

MULTI_GPU_UNAVAILABLE = torch.cuda.device_count() <= 1
TT_STABILITY_TESTS = os.environ.get("TT_STABILITY_TESTS", False)
if TT_STABILITY_TESTS:
    default_template = parse_model_template(
        os.path.join("src/otx/algorithms/action/configs", "classification", "x3d", "template.yaml")
    )
    templates = [default_template] * 100
    templates_ids = [template.model_template_id + f"-{i+1}" for i, template in enumerate(templates)]
else:
    templates = Registry("src/otx/algorithms/action").filter(task_type="ACTION_CLASSIFICATION").templates
    templates_ids = [template.model_template_id for template in templates]


class TestToolsOTXActionClassification:
    @e2e_pytest_component
    @pytest.mark.parametrize("template", templates, ids=templates_ids)
    def test_otx_train(self, template, tmp_dir_path):
        tmp_dir_path = tmp_dir_path / "action_cls"
        otx_train_testing(template, tmp_dir_path, otx_dir, args)

    @e2e_pytest_component
    @pytest.mark.skipif(TT_STABILITY_TESTS, reason="This is TT_STABILITY_TESTS")
    @pytest.mark.parametrize("template", templates, ids=templates_ids)
    def test_otx_resume(self, template, tmp_dir_path):
        tmp_dir_path = tmp_dir_path / "action_cls/test_resume"
        otx_resume_testing(template, tmp_dir_path, otx_dir, args)
        template_work_dir = get_template_dir(template, tmp_dir_path)
        args1 = copy.deepcopy(args)
        args1["train_params"] = resume_params
        args1[
            "--resume-from"
        ] = f"{template_work_dir}/trained_for_resume_{template.model_template_id}/models/weights.pth"
        otx_resume_testing(template, tmp_dir_path, otx_dir, args1)

    @e2e_pytest_component
    @pytest.mark.skipif(TT_STABILITY_TESTS, reason="This is TT_STABILITY_TESTS")
    @pytest.mark.parametrize("template", templates, ids=templates_ids)
    def test_otx_eval(self, template, tmp_dir_path):
        tmp_dir_path = tmp_dir_path / "action_cls"
        otx_eval_testing(template, tmp_dir_path, otx_dir, args)

    @e2e_pytest_component
    @pytest.mark.skipif(TT_STABILITY_TESTS, reason="This is TT_STABILITY_TESTS")
    @pytest.mark.parametrize("template", templates, ids=templates_ids)
    def test_otx_export(self, template, tmp_dir_path):
        tmp_dir_path = tmp_dir_path / "action_cls"
        otx_export_testing(template, tmp_dir_path)

    @e2e_pytest_component
    @pytest.mark.skipif(TT_STABILITY_TESTS, reason="This is TT_STABILITY_TESTS")
    @pytest.mark.parametrize("template", templates, ids=templates_ids)
    def test_otx_export_fp16(self, template, tmp_dir_path):
        tmp_dir_path = tmp_dir_path / "action_cls"
        otx_export_testing(template, tmp_dir_path, half_precision=True)

    @e2e_pytest_component
    @pytest.mark.skipif(TT_STABILITY_TESTS, reason="This is TT_STABILITY_TESTS")
    @pytest.mark.parametrize("template", templates, ids=templates_ids)
    def test_otx_export_onnx(self, template, tmp_dir_path):
        tmp_dir_path = tmp_dir_path / "action_cls"
        otx_export_testing(template, tmp_dir_path, half_precision=False, is_onnx=True)

    @e2e_pytest_component
    @pytest.mark.skipif(TT_STABILITY_TESTS, reason="This is TT_STABILITY_TESTS")
    @pytest.mark.parametrize("template", templates, ids=templates_ids)
    def test_otx_eval_openvino(self, template, tmp_dir_path):
        if template.model_template_id == "Custom_Action_Classification_MoViNet":
            pytest.xfail("Issue#2058: MoViNet inference fails in OV 2023.0")
        tmp_dir_path = tmp_dir_path / "action_cls"
        otx_eval_openvino_testing(template, tmp_dir_path, otx_dir, args, threshold=1.0)

    @e2e_pytest_component
    @pytest.mark.skipif(TT_STABILITY_TESTS, reason="This is TT_STABILITY_TESTS")
    @pytest.mark.parametrize("template", templates, ids=templates_ids)
    @pytest.mark.parametrize("bs_adapt_type", ["Safe", "Full"])
    def test_otx_train_auto_adapt_batch_size(self, template, tmp_dir_path, bs_adapt_type):
        adapting_bs_args = deepcopy(args)
        adapting_bs_args["train_params"].extend(["--learning_parameters.auto_adapt_batch_size", bs_adapt_type])
        tmp_dir_path = tmp_dir_path / f"action_cls_auto_adapt_{bs_adapt_type}_batch_size"
        otx_train_testing(template, tmp_dir_path, otx_dir, adapting_bs_args)

    @e2e_pytest_component
    @pytest.mark.skipif(TT_STABILITY_TESTS, reason="This is TT_STABILITY_TESTS")
    @pytest.mark.parametrize("template", templates, ids=templates_ids)
    def test_otx_train_auto_adapt_num_workers(self, template, tmp_dir_path):
        adapting_num_workers_args = deepcopy(args)
        adapting_num_workers_args["train_params"].extend(["--learning_parameters.auto_num_workers", "True"])
        tmp_dir_path = tmp_dir_path / f"action_cls_auto_adapt_num_workers"
        otx_train_testing(template, tmp_dir_path, otx_dir, adapting_num_workers_args)

    @e2e_pytest_component
    @pytest.mark.skipif(MULTI_GPU_UNAVAILABLE, reason="The number of gpu is insufficient")
    @pytest.mark.skipif(TT_STABILITY_TESTS, reason="This is TT_STABILITY_TESTS")
    @pytest.mark.parametrize("template", templates, ids=templates_ids)
    def test_otx_multi_gpu_train(self, template, tmp_dir_path):
        tmp_dir_path = tmp_dir_path / "action_cls/test_multi_gpu"
        args1 = deepcopy(args)
        args1["--gpus"] = "0,1"
        otx_train_testing(template, tmp_dir_path, otx_dir, args1)
