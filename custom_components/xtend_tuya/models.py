from __future__ import annotations

from typing import Any
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaDPCodeTypeInformationWrapper,
    TuyaCustomerDevice,
)
from .type_information import XTIntegerNoMinMaxCheckTypeInformation

class XTDPCodeIntegerNoMinMaxCheckWrapper(TuyaDPCodeTypeInformationWrapper[XTIntegerNoMinMaxCheckTypeInformation]):
    """Simple wrapper for IntegerTypeInformation values."""

    _DPTYPE = XTIntegerNoMinMaxCheckTypeInformation

    def __init__(self, dpcode: str, type_information: XTIntegerNoMinMaxCheckTypeInformation) -> None:
        """Init DPCodeIntegerWrapper."""
        super().__init__(dpcode, type_information)
        self.native_unit = type_information.unit
        self.min_value = self.type_information.scale_value(type_information.min)
        self.max_value = self.type_information.scale_value(type_information.max)
        self.value_step = self.type_information.scale_value(type_information.step)

    def _convert_value_to_raw_value(self, device: TuyaCustomerDevice, value: Any) -> Any:
        """Convert a Home Assistant value back to a raw device value."""
        return round(value * (10**self.type_information.scale))