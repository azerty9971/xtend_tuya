from __future__ import annotations

from .ha_tuya_integration.tuya_integration_imports import (
    TuyaDPCodeIntegerWrapper,
    TuyaCustomerDevice,
    tuya_type_information_should_log_warning,
)
from .const import (
    LOGGER,
)


class XTDPCodeIntegerNoMinMaxCheckWrapper(TuyaDPCodeIntegerWrapper):
    """Simple wrapper for IntegerTypeInformation values."""

    def read_device_status(self, device: TuyaCustomerDevice) -> float | None:
        """Read and process raw value against this type information."""
        if (raw_value := device.status.get(self.dpcode)) is None:
            return None
        # Validate input against defined range
        if not isinstance(raw_value, int):
            if tuya_type_information_should_log_warning(
                device.id, f"integer_out_range|{self.dpcode}|{raw_value}"
            ):
                LOGGER.warning(
                    "Found invalid integer value `%s` for datapoint `%s` in product "
                    "id `%s`, expected integer value between %s and %s; please report "
                    "this defect to Tuya support",
                    raw_value,
                    self.dpcode,
                    device.product_id,
                    self.type_information.min,
                    self.type_information.max,
                )

            return None
        return self.type_information.scale_value(raw_value)

    def _convert_value_to_raw_value(
        self, device: TuyaCustomerDevice, value: float
    ) -> int:
        """Convert a Home Assistant value back to a raw device value."""
        new_value = self.type_information.scale_value_back(value)
        return new_value
