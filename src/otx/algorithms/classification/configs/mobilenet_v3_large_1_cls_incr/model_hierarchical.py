"""MobileNet-V3-large-1 for hierarchical config."""
# Copyright (C) 2023 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

# pylint: disable=invalid-name

_base_ = ["../../../../recipes/stages/classification/incremental.yaml", "../base/models/mobilenet_v3.py"]

model = dict(
    type="CustomImageClassifier",
    task="classification",
    backbone=dict(mode="large"),
    head=dict(
        type="CustomHierarchicalNonLinearClsHead",
        in_channels=960,
        hid_channels=1280,
        multilabel_loss=dict(
            type="AsymmetricLossWithIgnore",
            gamma_pos=0.0,
            gamma_neg=4.0,
        ),
    ),
)
