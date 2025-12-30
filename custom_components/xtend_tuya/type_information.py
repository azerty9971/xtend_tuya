from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaIntegerTypeInformation,
    TuyaCustomerDevice,
    tuya_type_information_should_log_warning,
)
from .const import LOGGER

@dataclass(kw_only=True)
class XTIntegerNoMinMaxCheckTypeInformation(TuyaIntegerTypeInformation):
    """Extended Integer Type Information with remapping support."""

    def process_raw_value(
        self, raw_value: Any | None, device: TuyaCustomerDevice
    ) -> float | None:
        """Read and process raw value against this type information."""
        if raw_value is None:
            return None
        # Validate input against defined range
        if not isinstance(raw_value, int):
            if tuya_type_information_should_log_warning(
                device.id, f"integer_out_range|{self.dpcode}|{raw_value}"
            ):
                LOGGER.warning(
                    "Found invalid integer value `%s` for datapoint `%s` in product "
                    "id `%s`, "
                    "this defect to Tuya support",
                    raw_value,
                    self.dpcode,
                    device.product_id,
                )

            return None
        return raw_value / (10**self.scale)