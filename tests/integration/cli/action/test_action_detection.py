"""Tests for Action Detection Task with OTX CLI"""
# Copyright (C) 2022 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import os

import pytest

from otx.api.entities.model_template import parse_model_template
from otx.cli.registry import Registry
from otx.cli.utils.tests import otx_eval_testing, otx_train_testing
from tests.test_suite.e2e_test_system import e2e_pytest_component

# Finetuning arguments
# TODO: Need to change sample dataset
args = {
    "--train-data-roots": "data/datumaro/cvat_dataset/action_detection/train",
    "--val-data-roots": "data/datumaro/cvat_dataset/action_detection/train",
    "--test-data-roots": "data/datumaro/cvat_dataset/action_detection/train",
    "train_params": ["params", "--learning_parameters.num_iters", "2", "--learning_parameters.batch_size", "4"],
}

otx_dir = os.getcwd()

TT_STABILITY_TESTS = os.environ.get("TT_STABILITY_TESTS", False)
if TT_STABILITY_TESTS:
    default_template = parse_model_template(
        os.path.join("otx/algorithms/action/configs", "detection", "x3d_fast_rcnn", "template.yaml")
    )
    templates = [default_template] * 100
    templates_ids = [template.model_template_id + f"-{i+1}" for i, template in enumerate(templates)]
else:
    templates = Registry("otx/algorithms/action").filter(task_type="ACTION_DETECTION").templates
    templates_ids = [template.model_template_id for template in templates]


class TestToolsOTXActionDetection:
    @e2e_pytest_component
    @pytest.mark.parametrize("template", templates, ids=templates_ids)
    def test_otx_train(self, template, tmp_dir_path):
        otx_train_testing(template, tmp_dir_path, otx_dir, args)

    @e2e_pytest_component
    @pytest.mark.skipif(TT_STABILITY_TESTS, reason="This is TT_STABILITY_TESTS")
    @pytest.mark.parametrize("template", templates, ids=templates_ids)
    def test_otx_eval(self, template, tmp_dir_path):
        otx_eval_testing(template, tmp_dir_path, otx_dir, args)
