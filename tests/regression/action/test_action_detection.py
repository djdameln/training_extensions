"""Tests for Action Detection with OTX CLI."""
# Copyright (C) 2022 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
import json
import os
from pathlib import Path
from timeit import default_timer as timer

import pytest

from otx.cli.registry import Registry
from tests.regression.regression_test_helpers import (
    REGRESSION_TEST_EPOCHS,
    TIME_LOG,
    RegressionTestConfig,
)
from tests.test_suite.e2e_test_system import e2e_pytest_component
from tests.test_suite.run_test_command import (
    otx_train_testing,
)

from tests.regression.regression_command import (
    regression_eval_testing,
    regression_openvino_testing,
    regression_deployment_testing,
    regression_nncf_eval_testing,
    regression_ptq_eval_testing,
    regression_train_time_testing,
    regression_eval_time_testing,
)


class TestRegressionActionDetection:
    REG_CATEGORY = "action"
    TASK_TYPE = "action_detection"
    TRAIN_TYPE = "supervised"
    LABEL_TYPE = "multi_class"

    TRAIN_PARAMS = ["--learning_parameters.num_iters", REGRESSION_TEST_EPOCHS]

    templates = Registry(f"src/otx/algorithms/{REG_CATEGORY}").filter(task_type=TASK_TYPE.upper()).templates
    templates_ids = [template.model_template_id for template in templates]

    reg_cfg: RegressionTestConfig

    @classmethod
    @pytest.fixture(scope="class")
    def reg_cfg(cls, tmp_dir_path):
        cls.reg_cfg = RegressionTestConfig(
            cls.TASK_TYPE,
            cls.TRAIN_TYPE,
            cls.LABEL_TYPE,
            os.getcwd(),
            train_params=cls.TRAIN_PARAMS,
            tmp_results_root=tmp_dir_path,
        )

        yield cls.reg_cfg

        print(f"writting regression result to {cls.reg_cfg.result_dir}/result_{cls.TRAIN_TYPE}_{cls.LABEL_TYPE}.json")
        with open(f"{cls.reg_cfg.result_dir}/result_{cls.TRAIN_TYPE}_{cls.LABEL_TYPE}.json", "w") as result_file:
            json.dump(cls.reg_cfg.result_dict, result_file, indent=4)

    def setup_method(self):
        self.performance = {}

    @e2e_pytest_component
    @pytest.mark.parametrize("template", templates, ids=templates_ids)
    def test_otx_train(self, reg_cfg, template, tmp_dir_path):
        self.performance[template.name] = {}

        tmp_dir_path = tmp_dir_path / reg_cfg.task_type
        train_start_time = timer()
        otx_train_testing(template, tmp_dir_path, reg_cfg.otx_dir, reg_cfg.args)
        train_elapsed_time = timer() - train_start_time

        infer_start_time = timer()
        test_result = regression_eval_testing(
            template,
            tmp_dir_path,
            reg_cfg.otx_dir,
            reg_cfg.args,
            reg_cfg.config_dict["regression_criteria"]["train"],
            self.performance[template.name],
        )
        infer_elapsed_time = timer() - infer_start_time

        self.performance[template.name][TIME_LOG["train_time"]] = round(train_elapsed_time, 3)
        self.performance[template.name][TIME_LOG["infer_time"]] = round(infer_elapsed_time, 3)
        reg_cfg.result_dict[reg_cfg.task_type][reg_cfg.label_type][reg_cfg.train_type]["train"].append(self.performance)

        assert test_result["passed"] is True, test_result["log"]

    @e2e_pytest_component
    @pytest.mark.parametrize("template", templates, ids=templates_ids)
    def test_otx_train_kpi_test(self, reg_cfg, template):
        performance = reg_cfg.get_template_performance(template)

        kpi_train_result = regression_train_time_testing(
            train_time_criteria=reg_cfg.config_dict["kpi_e2e_train_time_criteria"]["train"],
            e2e_train_time=performance[template.name][TIME_LOG["train_time"]],
            template=template,
        )

        kpi_eval_result = regression_eval_time_testing(
            eval_time_criteria=reg_cfg.config_dict["kpi_e2e_eval_time_criteria"]["train"],
            e2e_eval_time=performance[template.name][TIME_LOG["infer_time"]],
            template=template,
        )

        assert kpi_train_result["passed"] is True, kpi_train_result["log"]
        assert kpi_eval_result["passed"] is True, kpi_eval_result["log"]
