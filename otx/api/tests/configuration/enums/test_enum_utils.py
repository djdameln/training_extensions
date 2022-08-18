# Copyright (C) 2021-2022 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import pytest

from otx.api.configuration.enums.config_element_type import ConfigElementType
from otx.api.configuration.enums.utils import get_enum_names
from otx.api.tests.constants.otx.api_components import OtxSdkComponent
from otx.api.tests.constants.requirements import Requirements


@pytest.mark.components(OtxSdkComponent.otx.api)
class TestMetadataKeys:
    @pytest.mark.priority_medium
    @pytest.mark.unit
    @pytest.mark.reqids(Requirements.REQ_1)
    def test_get_enum_names(self):
        """
        <b>Description:</b>
        Check "get_enum_names" function

        <b>Input data:</b>
        Enum object

        <b>Expected results:</b>
        Test passes if list returned by "get_enum_names" function is equal to expected
        """
        assert get_enum_names(ConfigElementType) == [
            "INTEGER",
            "FLOAT",
            "BOOLEAN",
            "FLOAT_SELECTABLE",
            "SELECTABLE",
            "PARAMETER_GROUP",
            "CONFIGURABLE_PARAMETERS",
            "RULE",
            "UI_RULES",
        ]
