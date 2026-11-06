"""Sensors of the dé EV charger.

Most measurements are JSON documents stored in String DPCodes, each sensor
reads one field of such a document.
"""

from __future__ import annotations
import json
from typing import Any
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.util import dt as dt_util
from ...sensor import (
    XTSensorEntityDescription,
)
from ...ha_tuya_integration.tuya_integration_imports import (
    TuyaCustomerDevice,
    TuyaDPCodeEnumWrapper,
    TuyaDPCodeIntegerWrapper,
    TuyaDPCodeStringWrapper,
)
from .const import (
    CHARGE_MODES,
    DE_EV_CHARGER_CATEGORY,
    WORK_ST_DEBUG_STATES,
    WORK_STATES,
    DeEVChargerDPCode,
)


class DeEVJsonFieldWrapper(TuyaDPCodeStringWrapper[Any]):
    """Read a single field of a String DPCode holding a JSON document.

    Subclasses (see json_field_wrapper) define the path to the field, an
    optional divider, an optional mapping or the datetime conversion.
    """

    json_path: tuple[str | int, ...] = ()
    value_divider: float | None = None
    value_mapping: dict[int, str] | None = None
    is_datetime: bool = False

    def read_device_status(self, device: TuyaCustomerDevice) -> Any:
        """Read the device value for the dpcode."""
        value = self._read_dpcode_value(device)
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                return None
        for path_element in self.json_path:
            try:
                value = value[path_element]  # type: ignore
            except (KeyError, IndexError, TypeError):
                return None
        if value is None:
            return None
        try:
            if self.value_mapping is not None:
                return self.value_mapping.get(int(value))
            if self.value_divider is not None:
                return float(value) / self.value_divider
            if self.is_datetime:
                if (date_value := dt_util.parse_datetime(str(value))) is None:
                    return None
                if date_value.tzinfo is None:
                    date_value = date_value.replace(
                        tzinfo=dt_util.get_default_time_zone()
                    )
                return date_value
        except (TypeError, ValueError):
            return None
        return value

    def _convert_value_to_raw_value(
        self, device: TuyaCustomerDevice, value: Any
    ) -> Any:
        raise NotImplementedError


def json_field_wrapper(
    *json_path: str | int,
    divider: float | None = None,
    native_unit: str | None = None,
    suggested_unit: str | None = None,
    value_mapping: dict[int, str] | None = None,
    is_datetime: bool = False,
) -> tuple[type[DeEVJsonFieldWrapper], ...]:
    """Build a wrapper class reading one field of a JSON String DPCode."""
    wrapper = type(
        "DeEVJsonFieldWrapper_" + "_".join(str(p) for p in json_path),
        (DeEVJsonFieldWrapper,),
        {
            "json_path": json_path,
            "value_divider": divider,
            "native_unit": native_unit,
            "suggested_unit": suggested_unit,
            "value_mapping": value_mapping,
            "is_datetime": is_datetime,
        },
    )
    return (wrapper,)


class DeEVWorkStateWrapper(TuyaDPCodeIntegerWrapper[str]):
    """Map the Integer work state to an enum state."""

    def read_device_status(self, device: TuyaCustomerDevice) -> str | None:  # type: ignore[override]
        """Read the device value for the dpcode."""
        if (value := device.status.get(self.dpcode)) is None:
            return None
        try:
            return WORK_STATES.get(int(value))
        except (TypeError, ValueError):
            return None


class DeEVLowerCaseEnumWrapper(TuyaDPCodeEnumWrapper[str]):
    """Return the Enum value in lower case (for state translations)."""

    def read_device_status(self, device: TuyaCustomerDevice) -> str | None:  # type: ignore[override]
        """Read the device value for the dpcode."""
        if (value := super().read_device_status(device)) is None:
            return None
        return str(value).lower()


def _phase_sensors(phase: str) -> tuple[XTSensorEntityDescription, ...]:
    """Voltage/current/power sensors of one phase of x_metrics."""
    lower_phase = phase.lower()
    return (
        XTSensorEntityDescription(
            key=f"{DeEVChargerDPCode.X_METRICS}_{lower_phase}_voltage",
            dpcode=DeEVChargerDPCode.X_METRICS,
            translation_key=f"qt_ev_{lower_phase}_voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
            wrapper_class=json_field_wrapper(
                phase, 0, divider=10, native_unit=UnitOfElectricPotential.VOLT
            ),
        ),
        XTSensorEntityDescription(
            key=f"{DeEVChargerDPCode.X_METRICS}_{lower_phase}_current",
            dpcode=DeEVChargerDPCode.X_METRICS,
            translation_key=f"qt_ev_{lower_phase}_current",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
            wrapper_class=json_field_wrapper(
                phase, 1, divider=10, native_unit=UnitOfElectricCurrent.AMPERE
            ),
        ),
        XTSensorEntityDescription(
            key=f"{DeEVChargerDPCode.X_METRICS}_{lower_phase}_power",
            dpcode=DeEVChargerDPCode.X_METRICS,
            translation_key=f"qt_ev_{lower_phase}_power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
            wrapper_class=json_field_wrapper(
                phase, 2, divider=10, native_unit=UnitOfPower.KILO_WATT
            ),
        ),
    )


DE_EV_CHARGER_SENSORS: dict[str, tuple[XTSensorEntityDescription, ...]] = {
    DE_EV_CHARGER_CATEGORY: (
        XTSensorEntityDescription(
            key=DeEVChargerDPCode.X_WORK_STATE,
            translation_key="qt_ev_work_state",
            device_class=SensorDeviceClass.ENUM,
            options=list(WORK_STATES.values()),
            wrapper_class=(DeEVWorkStateWrapper,),
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DeEVChargerDPCode.X_WORK_ST_DEBUG,
            translation_key="qt_ev_work_st_debug",
            device_class=SensorDeviceClass.ENUM,
            options=WORK_ST_DEBUG_STATES,
            entity_category=EntityCategory.DIAGNOSTIC,
            wrapper_class=(DeEVLowerCaseEnumWrapper,),
            entity_registry_enabled_default=False,
        ),
        *_phase_sensors("L1"),
        *_phase_sensors("L2"),
        *_phase_sensors("L3"),
        XTSensorEntityDescription(
            key=f"{DeEVChargerDPCode.X_METRICS}_power",
            dpcode=DeEVChargerDPCode.X_METRICS,
            translation_key="qt_ev_power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=1,
            wrapper_class=json_field_wrapper(
                "p", divider=10, native_unit=UnitOfPower.KILO_WATT
            ),
        ),
        XTSensorEntityDescription(
            key=f"{DeEVChargerDPCode.X_METRICS}_temperature",
            dpcode=DeEVChargerDPCode.X_METRICS,
            translation_key="qt_ev_temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            suggested_display_precision=1,
            wrapper_class=json_field_wrapper(
                "t", divider=10, native_unit=UnitOfTemperature.CELSIUS
            ),
        ),
        XTSensorEntityDescription(
            key=f"{DeEVChargerDPCode.X_METRICS}_session_duration",
            dpcode=DeEVChargerDPCode.X_METRICS,
            translation_key="qt_ev_session_duration",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
            wrapper_class=json_field_wrapper(
                "d",
                divider=10,
                native_unit=UnitOfTime.SECONDS,
                suggested_unit=UnitOfTime.MINUTES,
            ),
        ),
        XTSensorEntityDescription(
            key=f"{DeEVChargerDPCode.X_METRICS}_session_energy",
            dpcode=DeEVChargerDPCode.X_METRICS,
            translation_key="qt_ev_session_energy",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            suggested_display_precision=1,
            wrapper_class=json_field_wrapper(
                "e", divider=10, native_unit=UnitOfEnergy.KILO_WATT_HOUR
            ),
        ),
        XTSensorEntityDescription(
            key=f"{DeEVChargerDPCode.X_CHARGER_INFO}_total_energy",
            dpcode=DeEVChargerDPCode.X_CHARGER_INFO,
            translation_key="qt_ev_total_energy",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            suggested_display_precision=1,
            wrapper_class=json_field_wrapper(
                "e", divider=10, native_unit=UnitOfEnergy.KILO_WATT_HOUR
            ),
        ),
        XTSensorEntityDescription(
            key=f"{DeEVChargerDPCode.X_CHARGER_INFO}_firmware",
            dpcode=DeEVChargerDPCode.X_CHARGER_INFO,
            translation_key="qt_ev_firmware",
            entity_category=EntityCategory.DIAGNOSTIC,
            wrapper_class=json_field_wrapper("fv"),
        ),
        XTSensorEntityDescription(
            key=f"{DeEVChargerDPCode.X_CHARGER_INFO}_rcd_type",
            dpcode=DeEVChargerDPCode.X_CHARGER_INFO,
            translation_key="qt_ev_rcd_type",
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            wrapper_class=json_field_wrapper("r"),
        ),
        XTSensorEntityDescription(
            key=f"{DeEVChargerDPCode.X_CHARGER_INFO}_cp_voltage",
            dpcode=DeEVChargerDPCode.X_CHARGER_INFO,
            translation_key="qt_ev_cp_voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            suggested_display_precision=1,
            wrapper_class=json_field_wrapper(
                "cp", divider=1, native_unit=UnitOfElectricPotential.VOLT
            ),
        ),
        XTSensorEntityDescription(
            key=f"{DeEVChargerDPCode.X_CHARGE_HISTORY}_start",
            dpcode=DeEVChargerDPCode.X_CHARGE_HISTORY,
            translation_key="qt_ev_last_session_start",
            device_class=SensorDeviceClass.TIMESTAMP,
            wrapper_class=json_field_wrapper("t", is_datetime=True),
            skip_uom_validation=True,
        ),
        XTSensorEntityDescription(
            key=f"{DeEVChargerDPCode.X_CHARGE_HISTORY}_duration",
            dpcode=DeEVChargerDPCode.X_CHARGE_HISTORY,
            translation_key="qt_ev_last_session_duration",
            device_class=SensorDeviceClass.DURATION,
            suggested_display_precision=0,
            wrapper_class=json_field_wrapper(
                "d",
                divider=1,
                native_unit=UnitOfTime.SECONDS,
                suggested_unit=UnitOfTime.MINUTES,
            ),
        ),
        XTSensorEntityDescription(
            key=f"{DeEVChargerDPCode.X_CHARGE_HISTORY}_energy",
            dpcode=DeEVChargerDPCode.X_CHARGE_HISTORY,
            translation_key="qt_ev_last_session_energy",
            device_class=SensorDeviceClass.ENERGY,
            suggested_display_precision=1,
            wrapper_class=json_field_wrapper(
                "c", divider=10, native_unit=UnitOfEnergy.KILO_WATT_HOUR
            ),
        ),
        XTSensorEntityDescription(
            key=f"{DeEVChargerDPCode.X_ALARM}_code",
            dpcode=DeEVChargerDPCode.X_ALARM,
            translation_key="qt_ev_last_alarm",
            device_class=SensorDeviceClass.ENUM,
            options=list(WORK_STATES.values()),
            entity_category=EntityCategory.DIAGNOSTIC,
            wrapper_class=json_field_wrapper("v", value_mapping=WORK_STATES),
        ),
        XTSensorEntityDescription(
            key=f"{DeEVChargerDPCode.X_ALARM}_time",
            dpcode=DeEVChargerDPCode.X_ALARM,
            translation_key="qt_ev_last_alarm_time",
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
            wrapper_class=json_field_wrapper("t", is_datetime=True),
            skip_uom_validation=True,
        ),
        XTSensorEntityDescription(
            key=f"{DeEVChargerDPCode.X_CHARGE_MODE}_mode",
            dpcode=DeEVChargerDPCode.X_CHARGE_MODE,
            translation_key="qt_ev_charge_mode",
            device_class=SensorDeviceClass.ENUM,
            options=list(CHARGE_MODES.values()),
            wrapper_class=json_field_wrapper("m", value_mapping=CHARGE_MODES),
        ),
    ),
}
