from __future__ import annotations


from .ha_tuya_integration.tuya_integration_imports import (
    TuyaDPCodeIntegerWrapper,
    TuyaCustomerDevice,
)
from .const import (
    LOGGER,  # noqa: F401
)


class XTDPCodeIntegerNoMinMaxCheckWrapper(TuyaDPCodeIntegerWrapper):
    """Simple wrapper for IntegerTypeInformation values."""

    def read_device_status(self, device: TuyaCustomerDevice) -> float | None:
        """Read and process raw value against this type information."""
        if (raw_value := device.status.get(self.dpcode)) is None:
            return None
        # Validate input against defined range
        if not isinstance(raw_value, int):
            return None
        return self.type_information.scale_value(raw_value)

    def _convert_value_to_raw_value(
        self, device: TuyaCustomerDevice, value: float
    ) -> int:
        """Convert a Home Assistant value back to a raw device value."""
        return round(value * (10 ** self.type_information.scale))