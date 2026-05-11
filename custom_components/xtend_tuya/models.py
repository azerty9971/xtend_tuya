from __future__ import annotations

import json
from typing import Any, Optional

from .ha_tuya_integration.tuya_integration_imports import (
    TuyaDPCodeIntegerWrapper,
    TuyaCustomerDevice,
    TuyaDPCodeTypeInformationWrapper,
    TuyaIntegerTypeInformation,
    TuyaBitmapTypeInformation,
    TuyaDPType,
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
        return round(value * (10 ** self.type_information.scale))


class XTDPCodeBitmapLabelsWrapper(TuyaDPCodeTypeInformationWrapper):  # type: ignore[type-arg]
    """Expose a BITMAP dpcode (bitmask) as a single sensor with decoded labels.

    Example output:
      - "0"      => no faults
      - "E01,E03" => bits set correspond to those labels

    Useful when you prefer ONE entity instead of multiple binary entities.
    """

    _DPTYPE = TuyaBitmapTypeInformation

    def __init__(
        self,
        dpcode: str,
        type_information: TuyaBitmapTypeInformation,
        labels: Optional[list[str]] = None,
    ) -> None:
        super().__init__(dpcode, type_information)
        self._labels: list[str] = labels or []

    @classmethod
    def find_dpcode(
        cls,
        device: TuyaCustomerDevice,
        dpcodes: str | tuple[str, ...] | None,
        *,
        prefer_function: bool = False,
    ) -> "XTDPCodeBitmapLabelsWrapper | None":
        """Find and return a wrapper for BITMAP DP codes."""
        if type_info := TuyaBitmapTypeInformation.find_dpcode(
            device, dpcodes, prefer_function=prefer_function
        ):
            dpcode = type_info.dpcode
            labels: list[str] = []
            sr = device.status_range.get(dpcode) or device.function.get(dpcode)
            if sr is not None:
                try:
                    values_dict = json.loads(sr.values) if sr.values else {}
                    labels = values_dict.get("label", [])
                except (ValueError, TypeError):
                    pass
            return cls(dpcode=dpcode, type_information=type_info, labels=labels)
        return None

    def read_device_status(self, device: TuyaCustomerDevice) -> str | None:
        """Return a comma-separated list of active fault labels (or '0' if none)."""
        raw = device.status.get(self.dpcode)
        if raw is None:
            return None
        if not isinstance(raw, int):
            return str(raw)
        if raw == 0:
            return "0"
        active: list[str] = []
        for bit, label in enumerate(self._labels):
            if raw & (1 << bit):
                active.append(label)
        if active:
            return ",".join(active)
        # Bits set but no labels provided — fall back to hex representation
        return hex(raw)
