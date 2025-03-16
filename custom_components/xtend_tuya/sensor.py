"""Support for Tuya sensors."""

from __future__ import annotations

import datetime

from dataclasses import dataclass, field


from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
    SensorExtraStoredData,
    RestoreSensor,
)
from homeassistant.const import (
    UnitOfEnergy,
    Platform,
    PERCENTAGE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant, callback, Event, EventStateChangedData, State
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change, async_call_later, async_track_state_change_event

from .util import (
    merge_device_descriptors,
    get_default_value
)

from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .const import (
    TUYA_DISCOVERY_NEW,
    DPCode,
    DPType,
    VirtualStates,  # noqa: F401
)
from .entity import (
    XTEntity,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaSensorEntity,
    TuyaSensorEntityDescription,
    TuyaDPCode,
    TuyaIntegerTypeData,
    TuyaDOMAIN,
    TuyaDEVICE_CLASS_UNITS,
)

@dataclass(frozen=True)
class XTSensorEntityDescription(TuyaSensorEntityDescription):
    """Describes XT sensor entity."""

    virtual_state: VirtualStates | None = None
    vs_copy_to_state: list[DPCode]  | None = field(default_factory=list)
    vs_copy_delta_to_state: list[DPCode]  | None = field(default_factory=list)

    reset_daily: bool = False
    reset_monthly: bool = False
    reset_yearly: bool = False
    reset_after_x_seconds: int = 0
    restoredata: bool = False

# Commonly used battery sensors, that are re-used in the sensors down below.
BATTERY_SENSORS: tuple[XTSensorEntityDescription, ...] = (
    XTSensorEntityDescription(
        key=DPCode.BATTERY_PERCENTAGE,
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    XTSensorEntityDescription(
        key=DPCode.BATTERY,  # Used by non-standard contact sensor implementations
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    XTSensorEntityDescription(
        key=DPCode.BATTERY_STATE,
        translation_key="battery_state",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    XTSensorEntityDescription(
        key=DPCode.BATTERY_VALUE,
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=DPCode.VA_BATTERY,
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=DPCode.RESIDUAL_ELECTRICITY,
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    XTSensorEntityDescription(
        key=DPCode.BATTERY_POWER,
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

#Commonlu sed energy sensors, that are re-used in the sensors down below.
CONSUMPTION_SENSORS: tuple[XTSensorEntityDescription, ...] = (
    XTSensorEntityDescription(
        key=DPCode.ADD_ELE,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME | VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        vs_copy_to_state=[DPCode.ADD_ELE2, DPCode.ADD_ELE_TODAY, DPCode.ADD_ELE_THIS_MONTH, DPCode.ADD_ELE_THIS_YEAR],
        translation_key="add_ele",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
    ),
    XTSensorEntityDescription(
        key=DPCode.ADD_ELE2,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME,
        vs_copy_delta_to_state=[DPCode.ADD_ELE2_TODAY, DPCode.ADD_ELE2_THIS_MONTH, DPCode.ADD_ELE2_THIS_YEAR],
        translation_key="add_ele2",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
    ),
    XTSensorEntityDescription(
        key=DPCode.ADD_ELE_TODAY,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="add_ele_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        reset_daily=True
    ),
    XTSensorEntityDescription(
        key=DPCode.ADD_ELE_THIS_MONTH,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="add_ele_this_month",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        reset_monthly=True
    ),
    XTSensorEntityDescription(
        key=DPCode.ADD_ELE_THIS_YEAR,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="add_ele_this_year",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        reset_yearly=True
    ),
    XTSensorEntityDescription(
        key=DPCode.ADD_ELE2_TODAY,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="add_ele2_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
        reset_daily=True
    ),
    XTSensorEntityDescription(
        key=DPCode.ADD_ELE2_THIS_MONTH,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="add_ele2_this_month",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
        reset_monthly=True
    ),
    XTSensorEntityDescription(
        key=DPCode.ADD_ELE2_THIS_YEAR,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="add_ele2_this_year",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
        reset_yearly=True
    ),
    XTSensorEntityDescription(
        key=DPCode.BALANCE_ENERGY,
        translation_key="balance_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=False,
    ),
    XTSensorEntityDescription(
        key=DPCode.CHARGE_ENERGY,
        translation_key="charge_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=False,
    ),
    XTSensorEntityDescription(
        key=DPCode.CHARGE_ENERGY_ONCE,
        translation_key="charge_energy_once",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=False,
    ),
    XTSensorEntityDescription(
        key=DPCode.CUR_POWER,
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
    XTSensorEntityDescription(
        key=DPCode.DEVICEKWH,
        translation_key="device_consumption",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
    XTSensorEntityDescription(
        key=DPCode.FORWARD_ENERGY_TOTAL,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME,
        vs_copy_delta_to_state=[DPCode.ADD_ELE2_TODAY, DPCode.ADD_ELE2_THIS_MONTH, DPCode.ADD_ELE2_THIS_YEAR],
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    XTSensorEntityDescription(
        key=DPCode.POWER_CONSUMPTION,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME | VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        vs_copy_to_state=[DPCode.ADD_ELE2, DPCode.ADD_ELE_TODAY, DPCode.ADD_ELE_THIS_MONTH, DPCode.ADD_ELE_THIS_YEAR],
        translation_key="add_ele",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
    ),
    XTSensorEntityDescription(
        key=DPCode.REVERSE_ENERGY_TOTAL,
        translation_key="gross_generation",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    XTSensorEntityDescription(
        key=DPCode.TOTAL_FORWARD_ENERGY,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME,
        vs_copy_delta_to_state=[DPCode.ADD_ELE2_TODAY, DPCode.ADD_ELE2_THIS_MONTH, DPCode.ADD_ELE2_THIS_YEAR],
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=False,
    ),
)

TEMPERATURE_SENSORS: tuple[XTSensorEntityDescription, ...] = (
    XTSensorEntityDescription(
        key=DPCode.TEMPERATURE,
        translation_key="temperature",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
    XTSensorEntityDescription(
        key=DPCode.TEMP_CURRENT,
        translation_key="temperature",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
    XTSensorEntityDescription(
        key=DPCode.TEMP_INDOOR,
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=DPCode.TEMP_VALUE,
        translation_key="temperature",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
    XTSensorEntityDescription(
        key=DPCode.TEMP_TOP,
        translation_key="temp_top",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
    XTSensorEntityDescription(
        key=DPCode.TEMP_BOTTOM,
        translation_key="temp_bottom",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
    XTSensorEntityDescription(
        key=DPCode.DEVICETEMP,
        translation_key="device_temperature",
        entity_registry_enabled_default=True,
    ),
    XTSensorEntityDescription(
        key=DPCode.DEVICETEMP2,
        translation_key="device_temperature2",
        entity_registry_enabled_default=True,
        entity_registry_visible_default=False,
    ),
    XTSensorEntityDescription(
        key=DPCode.TEMPSHOW,
        translation_key="temp_show",
        entity_registry_enabled_default=True,
    ),
)

HUMIDITY_SENSORS: tuple[XTSensorEntityDescription, ...] = (
    XTSensorEntityDescription(
        key=DPCode.HUMIDITY_VALUE,
        translation_key="humidity",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
    XTSensorEntityDescription(
        key=DPCode.HUMIDITY_INDOOR,
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

ELECTRICITY_SENSORS: tuple[XTSensorEntityDescription, ...] = (
    XTSensorEntityDescription(
        key=DPCode.A_CURRENT,
        translation_key="a_current",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=True,
        entity_registry_visible_default=False,
    ),
    XTSensorEntityDescription(
        key=DPCode.A_VOLTAGE,
        translation_key="a_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=True,
        entity_registry_visible_default=False,
    ),
    XTSensorEntityDescription(
        key=DPCode.B_CURRENT,
        translation_key="b_current",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=True,
        entity_registry_visible_default=False,
    ),
    XTSensorEntityDescription(
        key=DPCode.B_VOLTAGE,
        translation_key="b_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=True,
        entity_registry_visible_default=False,
    ),
    XTSensorEntityDescription(
        key=DPCode.CURRENT_YD,
        translation_key="current",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=False,
    ),
    XTSensorEntityDescription(
        key=DPCode.C_CURRENT,
        translation_key="c_current",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        entity_registry_enabled_default=True,
        entity_registry_visible_default=False,
    ),
    XTSensorEntityDescription(
        key=DPCode.C_VOLTAGE,
        translation_key="c_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=True,
        entity_registry_visible_default=False,
    ),
    XTSensorEntityDescription(
        key=DPCode.DEVICEKW,
        translation_key="device_power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=True,
    ),
    XTSensorEntityDescription(
        key=DPCode.DEVICEMAXSETA,
        translation_key="device_max_set_a",
        entity_registry_enabled_default=True,
        entity_registry_visible_default=False,
    ),
    XTSensorEntityDescription(
        key=DPCode.PHASEFLAG,
        translation_key="phaseflag",
        entity_registry_enabled_default=True,
        entity_registry_visible_default=False,
    ),
    XTSensorEntityDescription(
        key=DPCode.POWER_TOTAL,
        translation_key="power_total",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=True,
    ),
    XTSensorEntityDescription(
        key=DPCode.SIGLE_PHASE_POWER,
        translation_key="sigle_phase_power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        entity_registry_enabled_default=True,
    ),
    XTSensorEntityDescription(
        key=DPCode.VOL_YD,
        translation_key="voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
    ),
    XTSensorEntityDescription(
        key=DPCode.VOLTAGE_CURRENT,
        translation_key="voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
    ),
)

TIMER_SENSORS: tuple[XTSensorEntityDescription, ...] = (
    XTSensorEntityDescription(
        key=DPCode.CTIME,
        translation_key="ctime",
        entity_registry_enabled_default=True,
    ),
    XTSensorEntityDescription(
        key=DPCode.CTIME2,
        translation_key="ctime2",
        entity_registry_enabled_default=True,
        entity_registry_visible_default=False,
    ),
)

# All descriptions can be found here. Mostly the Integer data types in the
# default status set of each category (that don't have a set instruction)
# end up being a sensor.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
SENSORS: dict[str, tuple[XTSensorEntityDescription, ...]] = {
    "cl": (
        *BATTERY_SENSORS,
    ),
    "dbl": (
        XTSensorEntityDescription(
            key=DPCode.COUNTDOWN_LEFT,
            translation_key="countdown_left",
            entity_registry_enabled_default=False,
        ),
    ),
    "jtmspro": (
        XTSensorEntityDescription(
            key=DPCode.ALARM_LOCK,
            translation_key="jtmspro_alarm_lock",
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=DPCode.CLOSED_OPENED,
            translation_key="jtmspro_closed_opened",
            entity_registry_enabled_default=True,
        ),
        *ELECTRICITY_SENSORS,
        *BATTERY_SENSORS,
    ),
    # Switch
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
    "kg": (
        XTSensorEntityDescription(
            key=DPCode.ILLUMINANCE_VALUE,
            translation_key="illuminance_value",
            device_class=SensorDeviceClass.ILLUMINANCE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        *TEMPERATURE_SENSORS,
        *CONSUMPTION_SENSORS,
        *ELECTRICITY_SENSORS,
    ),
    "ms": (
        *BATTERY_SENSORS,
    ),
    # Automatic cat litter box
    # Note: Undocumented
    "msp": (
        XTSensorEntityDescription(
            key=DPCode.AUTO_DEORDRIZER,
            translation_key="auto_deordrizer",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.CALIBRATION,
            translation_key="calibration",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.CAPACITY_CALIBRATION,
            translation_key="capacity_calibration",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.CAT_WEIGHT,
            translation_key="cat_weight",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.CLEAN_NOTICE,
            translation_key="clean_notice",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.CLEAN_TASTE,
            translation_key="clean_taste",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=DPCode.CLEAN_TIME,
            translation_key="clean_time",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.DEODORIZATION_NUM,
            translation_key="ozone_concentration",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.DETECTION_SENSITIVITY,
            translation_key="detection_sensitivity",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.EXCRETION_TIMES_DAY,
            translation_key="excretion_times_day",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.EXCRETION_TIME_DAY,
            translation_key="excretion_time_day",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.HISTORY,
            translation_key="msp_history",
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.INDUCTION_CLEAN,
            translation_key="induction_clean",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.INDUCTION_DELAY,
            translation_key="induction_delay",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.INDUCTION_INTERVAL,
            translation_key="induction_interval",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.MONITORING,
            translation_key="monitoring",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=DPCode.NET_NOTICE,
            translation_key="net_notice",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=DPCode.NOT_DISTURB,
            translation_key="not_disturb",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.NOTIFICATION_STATUS,
            translation_key="notification_status",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=DPCode.NUMBER,
            translation_key="number",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=DPCode.ODOURLESS,
            translation_key="odourless",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=DPCode.PEDAL_ANGLE,
            translation_key="pedal_angle",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=DPCode.PIR_RADAR,
            translation_key="pir_radar",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=DPCode.SAND_SURFACE_CALIBRATION,
            translation_key="sand_surface_calibration",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.SMART_CLEAN,
            translation_key="smart_clean",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.STORE_FULL_NOTIFY,
            translation_key="store_full_notify",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.TOILET_NOTICE,
            translation_key="toilet_notice",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.UNIT,
            translation_key="unit",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.USAGE_TIMES,
            translation_key="usage_times",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.WORK_STAT,
            translation_key="work_stat",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        *TEMPERATURE_SENSORS,
    ),
    "ms_category": (
        XTSensorEntityDescription(
            key=DPCode.ALARM_LOCK,
            translation_key="ms_category_alarm_lock",
            entity_registry_enabled_default=False,
            reset_after_x_seconds=1
        ),
        *BATTERY_SENSORS,
    ),
    "mzj": (
        XTSensorEntityDescription(
            key=DPCode.WORK_STATUS,
            translation_key="mzj_work_status",
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.REMAININGTIME,
            translation_key="remaining_time",
            entity_registry_enabled_default=True,
        ),
        *TEMPERATURE_SENSORS,
    ),
    "hps": (
        XTSensorEntityDescription(
            key=DPCode.PRESENCE_STATE,
            translation_key="hps_presence_state",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        XTSensorEntityDescription(
            key=DPCode.TARGET_DISTANCE,
            translation_key="target_distance",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        XTSensorEntityDescription(
            key=DPCode.LDR,
            translation_key="ldr",
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    "qccdz": (
        XTSensorEntityDescription(
            key=DPCode.WORK_STATE,
            translation_key="qccdz_work_state",
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.CONNECTION_STATE,
            translation_key="qccdz_connection_state",
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.SYSTEM_VERSION,
            translation_key="system_version",
            entity_registry_enabled_default=True,
            entity_registry_visible_default=False,
        ),
        XTSensorEntityDescription(
            key=DPCode.DEVICESTATE,
            translation_key="qccdz_devicestate",
            entity_registry_enabled_default=True,
        ),
        *CONSUMPTION_SENSORS,
        *TEMPERATURE_SENSORS,
        *ELECTRICITY_SENSORS,
        *TIMER_SENSORS,
    ),
    "sfkzq": (
        XTSensorEntityDescription(
            key=DPCode.WATER_ONCE,
            translation_key="water_once",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.WATER_TOTAL,
            translation_key="water_total",
            state_class=SensorStateClass.TOTAL_INCREASING,
            entity_registry_enabled_default=True,
        ),
    ),
    "slj": (
        XTSensorEntityDescription(
            key=DPCode.WATER_USE_DATA,
            translation_key="water_use_data",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.WATER_ONCE,
            translation_key="water_once",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.FLOW_VELOCITY,
            translation_key="flow_velocity",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        *ELECTRICITY_SENSORS,
    ),
    "smd": (
        XTSensorEntityDescription(
            key=DPCode.HEART_RATE,
            translation_key="heart_rate",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.RESPIRATORY_RATE,
            translation_key="respiratory_rate",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.SLEEP_STAGE,
            translation_key="sleep_stage",
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.TIME_GET_IN_BED,
            translation_key="time_get_in_bed",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.OFF_BED_TIME,
            translation_key="off_bed_time",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.CLCT_TIME,
            translation_key="clct_time",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
    ),
    "wk": (
        *BATTERY_SENSORS,
    ),
    "wnykq": (
        XTSensorEntityDescription(
            key=DPCode.IR_CONTROL,
            translation_key="wnykq_ir_control",
            entity_registry_enabled_default=True,
        ),
        *TEMPERATURE_SENSORS,
        *HUMIDITY_SENSORS,
    ),
    "wsdcg": (
        *TEMPERATURE_SENSORS,
    ),
    "xfj": (
        XTSensorEntityDescription(
            key=DPCode.PM25,
            translation_key="pm25",
            device_class=SensorDeviceClass.PM25,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        XTSensorEntityDescription(
            key=DPCode.ECO2,
            translation_key="concentration_carbon_dioxide",
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        XTSensorEntityDescription(
            key=DPCode.FILTER_LIFE,
            translation_key="filter_life",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        XTSensorEntityDescription(
            key=DPCode.TVOC,
            translation_key="tvoc",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        XTSensorEntityDescription(
            key=DPCode.AIR_QUALITY,
            translation_key="air_quality",
        ),
        *TEMPERATURE_SENSORS,
        *HUMIDITY_SENSORS,
    ),
    "ywcgq": (
        XTSensorEntityDescription(
            key=DPCode.LIQUID_STATE,
            translation_key="liquid_state",
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.LIQUID_DEPTH,
            translation_key="liquid_depth",
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=DPCode.LIQUID_LEVEL_PERCENT,
            translation_key="liquid_level_percent",
            entity_registry_enabled_default=True,
        ),
    ),
    #ZNRB devices don't send correct cloud data, for these devices use https://github.com/make-all/tuya-local instead
    #"znrb": (
    #    *CONSUMPTION_SENSORS,
    #    *TEMPERATURE_SENSORS,
    #),
}

# Socket (duplicate of `kg`)
# https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
SENSORS["cz"]   = SENSORS["kg"]
SENSORS["wkcz"] = SENSORS["kg"]
SENSORS["dlq"]  = SENSORS["kg"]
SENSORS["tdq"]  = SENSORS["kg"]
SENSORS["pc"]   = SENSORS["kg"]
SENSORS["aqcz"] = SENSORS["kg"]
SENSORS["zndb"] = SENSORS["kg"]

#Lock duplicates
SENSORS["videolock"] = SENSORS["jtmspro"]

async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya sensor dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    merged_descriptors = SENSORS
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.SENSOR):
        merged_descriptors = merge_device_descriptors(merged_descriptors, new_descriptor)

    @callback
    def async_discover_device(device_map) -> None:
        """Discover and add a discovered Tuya sensor."""
        entities: list[XTSensorEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if descriptions := merged_descriptors.get(device.category):
                    entities.extend(
                        XTSensorEntity(device, hass_data.manager, XTSensorEntityDescription(**description.__dict__))
                        for description in descriptions
                        if description.key in device.status
                    )

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors("sensors", merged_descriptors)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTSensorEntity(XTEntity, TuyaSensorEntity, RestoreSensor):
    """XT Sensor Entity."""

    entity_description: XTSensorEntityDescription
    _restored_data: SensorExtraStoredData | None = None

    def _replaced_constructor(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSensorEntityDescription,
    ) -> None:
        self.entity_description = description
        self._attr_unique_id = (
            f"{super().unique_id}{description.key}{description.subkey or ''}"
        )

        if int_type := self.find_dpcode(description.key, dptype=DPType.INTEGER):
            self._type_data = int_type
            self._type = DPType.INTEGER
            if description.native_unit_of_measurement is None:
                self._attr_native_unit_of_measurement = int_type.unit
        elif enum_type := self.find_dpcode(
            description.key, dptype=DPType.ENUM, prefer_function=True
        ):
            self._type_data = enum_type
            self._type = DPType.ENUM
        else:
            self._type = self.get_dptype(description.key)   #This is modified from TuyaSensorEntity's constructor

        # Logic to ensure the set device class and API received Unit Of Measurement
        # match Home Assistants requirements.
        if (
            self.device_class is not None
            and not self.device_class.startswith(TuyaDOMAIN)
            and description.native_unit_of_measurement is None
        ):
            # We cannot have a device class, if the UOM isn't set or the
            # device class cannot be found in the validation mapping.
            if (
                self.native_unit_of_measurement is None
                or self.device_class not in TuyaDEVICE_CLASS_UNITS
            ):
                self._attr_device_class = None
                return

            uoms = TuyaDEVICE_CLASS_UNITS[self.device_class]
            self._uom = uoms.get(self.native_unit_of_measurement) or uoms.get(
                self.native_unit_of_measurement.lower()
            )

            # Unknown unit of measurement, device class should not be used.
            if self._uom is None:
                self._attr_device_class = None
                return

            # Found unit of measurement, use the standardized Unit
            # Use the target conversion unit (if set)
            self._attr_native_unit_of_measurement = (
                self._uom.conversion_unit or self._uom.unit
            )

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSensorEntityDescription,
    ) -> None:
        """Init XT sensor."""
        try:
            super(XTSensorEntity, self).__init__(device, device_manager, description)
        except Exception:
            self._replaced_constructor(device=device, device_manager=device_manager, description=description)
        
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description

    def reset_value(self, _: datetime, manual_call: bool = False) -> None:
        if manual_call and self.cancel_reset_after_x_seconds:
            self.cancel_reset_after_x_seconds()
        self.cancel_reset_after_x_seconds = None
        value = self.device.status.get(self.entity_description.key)
        default_value = get_default_value(self._type)
        if value is None or value == default_value:
            return
        self.device.status[self.entity_description.key] = default_value
        self.schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        async def reset_status_daily(now: datetime.datetime) -> None:
            should_reset = False
            if self.entity_description.reset_daily:
                should_reset = True

            if self.entity_description.reset_monthly and now.day == 1:
                should_reset = True

            if self.entity_description.reset_yearly and now.day == 1 and now.month == 1:
                should_reset = True
            
            if should_reset:
                if device := self.device_manager.device_map.get(self.device.id, None):
                    if self.entity_description.key in device.status:
                        device.status[self.entity_description.key] = float(0)
                        if self.entity_description.state_class == SensorStateClass.TOTAL:
                            self.entity_description.last_reset = now
                        self.async_write_ha_state()

        if (
            self.entity_description.reset_daily 
        or  self.entity_description.reset_monthly 
        or  self.entity_description.reset_yearly 
        ):
            self.async_on_remove(
                async_track_time_change(
                    self.hass, reset_status_daily, hour=0, minute=0, second=0
                )
            )
        if self.entity_description.reset_after_x_seconds:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    self.entity_id,
                    self._on_state_change_event,
                )
            )
        
        if self.entity_description.restoredata:
            self._restored_data = await self.async_get_last_sensor_data()
            if self._restored_data is not None and self._restored_data.native_value is not None:
                # Scale integer/float value
                if isinstance(self._type_data, TuyaIntegerTypeData):
                    scaled_value_back = self._type_data.scale_value_back(self._restored_data.native_value)
                    self._restored_data.native_value = scaled_value_back

                if device := self.device_manager.device_map.get(self.device.id, None):
                    device.status[self.entity_description.key] = float(self._restored_data.native_value)
    
    @callback
    async def _on_state_change_event(self, event: Event[EventStateChangedData]):
        new_state: State = event.data.get("new_state")
        default_value = get_default_value(self._type)
        if not new_state.state or new_state.state == default_value:
            return
        if self.cancel_reset_after_x_seconds:
            self.cancel_reset_after_x_seconds()
        self.cancel_reset_after_x_seconds = async_call_later(self.hass, self.entity_description.reset_after_x_seconds, self.reset_value)
