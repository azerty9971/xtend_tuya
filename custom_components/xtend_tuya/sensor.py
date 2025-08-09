"""Support for Tuya sensors."""

from __future__ import annotations
from typing import cast
import datetime
from dataclasses import dataclass, field
from .const import LOGGER  # noqa: F401
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
from homeassistant.core import (
    HomeAssistant,
    callback,
    Event,
    EventStateChangedData,
    State,
    CALLBACK_TYPE,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_time_change,
    async_call_later,
    async_track_state_change_event,
)
from .util import (
    get_default_value,
    restrict_descriptor_category,
)
from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .const import (
    TUYA_DISCOVERY_NEW,
    XTDPCode,
    VirtualStates,  # noqa: F401
    XTDeviceEntityFunctions,
    CROSS_CATEGORY_DEVICE_DESCRIPTOR,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaSensorEntity,
    TuyaSensorEntityDescription,
    TuyaIntegerTypeData,
    TuyaDOMAIN,
    TuyaDEVICE_CLASS_UNITS,
    TuyaDPType,
)


@dataclass(frozen=True)
class XTSensorEntityDescription(TuyaSensorEntityDescription, frozen=True):
    """Describes XT sensor entity."""

    virtual_state: VirtualStates | None = None
    vs_copy_to_state: list[XTDPCode] | None = field(default_factory=list)
    vs_copy_delta_to_state: list[XTDPCode] | None = field(default_factory=list)

    reset_daily: bool = False
    reset_monthly: bool = False
    reset_yearly: bool = False
    reset_after_x_seconds: int = 0
    restoredata: bool = False
    refresh_device_after_load: bool = False
    recalculate_scale_for_percentage: bool = False
    recalculate_scale_for_percentage_threshold: int = (
        100  # Maximum percentage that the sensor can display (default = 100%)
    )

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSensorEntityDescription,
    ) -> XTSensorEntity:
        return XTSensorEntity(
            device=device, device_manager=device_manager, description=description
        )


# Commonly used battery sensors, that are re-used in the sensors down below.
BATTERY_SENSORS: tuple[XTSensorEntityDescription, ...] = (
    XTSensorEntityDescription(
        key=XTDPCode.BATTERY_PERCENTAGE,
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        recalculate_scale_for_percentage=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.BATTERY,  # Used by non-standard contact sensor implementations
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        recalculate_scale_for_percentage=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.BATTERY_STATE,
        translation_key="battery_state",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.BATTERY_VALUE,
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.VA_BATTERY,
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.RESIDUAL_ELECTRICITY,
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        recalculate_scale_for_percentage=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.BATTERY_POWER,
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

# Commonly used energy sensors, that are re-used in the sensors down below.
CONSUMPTION_SENSORS: tuple[XTSensorEntityDescription, ...] = (
    XTSensorEntityDescription(
        key=XTDPCode.ADD_ELE,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME
        | VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        vs_copy_to_state=[
            XTDPCode.ADD_ELE2,
            XTDPCode.ADD_ELE_TODAY,
            XTDPCode.ADD_ELE_THIS_MONTH,
            XTDPCode.ADD_ELE_THIS_YEAR,
        ],
        translation_key="add_ele",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ADD_ELE2,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME,
        vs_copy_delta_to_state=[
            XTDPCode.ADD_ELE2_TODAY,
            XTDPCode.ADD_ELE2_THIS_MONTH,
            XTDPCode.ADD_ELE2_THIS_YEAR,
        ],
        translation_key="add_ele2",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ADD_ELE_TODAY,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="add_ele_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        reset_daily=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ADD_ELE_THIS_MONTH,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="add_ele_this_month",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        reset_monthly=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ADD_ELE_THIS_YEAR,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="add_ele_this_year",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        reset_yearly=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ADD_ELE2_TODAY,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="add_ele2_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
        reset_daily=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ADD_ELE2_THIS_MONTH,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="add_ele2_this_month",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
        reset_monthly=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ADD_ELE2_THIS_YEAR,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="add_ele2_this_year",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
        reset_yearly=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.BALANCE_ENERGY,
        translation_key="balance_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        restoredata=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CHARGE_ENERGY,
        translation_key="charge_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        restoredata=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CHARGE_ENERGY_ONCE,
        translation_key="charge_energy_once",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        restoredata=False,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.DEVICEKWH,
        translation_key="device_consumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        restoredata=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ELECTRIC,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME
        | VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        vs_copy_to_state=[
            XTDPCode.ELECTRIC_TODAY,
            XTDPCode.ELECTRIC_THIS_MONTH,
            XTDPCode.ELECTRIC_THIS_YEAR,
        ],
        translation_key="electric",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        restoredata=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ELECTRIC_TODAY,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="electric_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        restoredata=True,
        reset_daily=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ELECTRIC_THIS_MONTH,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="electric_this_month",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        restoredata=True,
        reset_monthly=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ELECTRIC_THIS_YEAR,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="electric_this_year",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        reset_yearly=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ENERGYCONSUMED,
        translation_key="energyconsumed",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ENERGYCONSUMEDA,
        translation_key="energyconsumeda",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ENERGYCONSUMEDB,
        translation_key="energyconsumedb",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ENERGYCONSUMEDC,
        translation_key="energyconsumedc",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.FORWARD_ENERGY_TOTAL,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME,
        vs_copy_delta_to_state=[
            XTDPCode.ADD_ELE2_TODAY,
            XTDPCode.ADD_ELE2_THIS_MONTH,
            XTDPCode.ADD_ELE2_THIS_YEAR,
        ],
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        restoredata=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.POWER_CONSUMPTION,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME
        | VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        vs_copy_to_state=[
            XTDPCode.ADD_ELE2,
            XTDPCode.ADD_ELE_TODAY,
            XTDPCode.ADD_ELE_THIS_MONTH,
            XTDPCode.ADD_ELE_THIS_YEAR,
        ],
        translation_key="add_ele",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.REVERSE_ENERGY_A,
        translation_key="gross_generation_a",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.REVERSE_ENERGY_B,
        translation_key="gross_generation_b",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.REVERSE_ENERGY_C,
        translation_key="gross_generation_c",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.REVERSE_ENERGY_T,
        translation_key="gross_generation",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.REVERSE_ENERGY_TOTAL,
        translation_key="gross_generation",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        restoredata=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TOTALENERGYCONSUMED,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME,
        vs_copy_delta_to_state=[
            XTDPCode.ADD_ELE2_TODAY,
            XTDPCode.ADD_ELE2_THIS_MONTH,
            XTDPCode.ADD_ELE2_THIS_YEAR,
        ],
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TOTAL_FORWARD_ENERGY,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME,
        vs_copy_delta_to_state=[
            XTDPCode.ADD_ELE2_TODAY,
            XTDPCode.ADD_ELE2_THIS_MONTH,
            XTDPCode.ADD_ELE2_THIS_YEAR,
        ],
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        restoredata=True,
    ),
)

TEMPERATURE_SENSORS: tuple[XTSensorEntityDescription, ...] = (
    XTSensorEntityDescription(
        key=XTDPCode.TEMPERATURE,
        translation_key="temperature",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TEMPERATURE2,
        translation_key="temperature",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TEMP2,
        translation_key="temperature",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TEMP_CURRENT,
        translation_key="temperature",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TEMP_INDOOR,
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TEMP_VALUE,
        translation_key="temperature",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TEMP_TOP,
        translation_key="temp_top",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TEMP_BOTTOM,
        translation_key="temp_bottom",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.DEVICETEMP,
        translation_key="device_temperature",
    ),
    XTSensorEntityDescription(
        key=XTDPCode.DEVICETEMP2,
        translation_key="device_temperature2",
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TEMPSHOW,
        translation_key="temp_show",
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TEMP_ALARM,
        translation_key="temp_alarm",
    ),
)

HUMIDITY_SENSORS: tuple[XTSensorEntityDescription, ...] = (
    XTSensorEntityDescription(
        key=XTDPCode.HUMIDITY,
        translation_key="humidity",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.HUMIDITY1,
        translation_key="humidity",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.HUMIDITY_VALUE,
        translation_key="humidity",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.HUMIDITY_INDOOR,
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.HUM_ALARM,
        translation_key="hum_alarm",
    ),
)

ELECTRICITY_SENSORS: tuple[XTSensorEntityDescription, ...] = (
    XTSensorEntityDescription(
        key=XTDPCode.POWER_A,
        translation_key="power_a",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.POWER_B,
        translation_key="power_b",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CURRENT_A,
        translation_key="current_a",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CURRENT_B,
        translation_key="current_b",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.VOLTAGE_A,
        translation_key="voltage_a",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.DIRECTION_A,
        translation_key="direction_a",
    ),
    XTSensorEntityDescription(
        key=XTDPCode.DIRECTION_B,
        translation_key="direction_b",
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ACHZ,
        translation_key="achz",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.FREQUENCY,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ACTIVEPOWER,
        translation_key="activepower",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ACTIVEPOWERA,
        translation_key="activepowera",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ACTIVEPOWERB,
        translation_key="activepowerb",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ACTIVEPOWERC,
        translation_key="activepowerc",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ACV,
        translation_key="acv",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ACI,
        translation_key="aci",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.A_CURRENT,
        translation_key="a_current",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.A_VOLTAGE,
        translation_key="a_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.B_CURRENT,
        translation_key="b_current",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.B_VOLTAGE,
        translation_key="b_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CUR_POWER,
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CURRENT,
        translation_key="current",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CURRENTA,
        translation_key="currenta",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CURRENTB,
        translation_key="currentb",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CURRENTC,
        translation_key="currentc",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CURRENT_YD,
        translation_key="current",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.C_CURRENT,
        translation_key="c_current",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.C_VOLTAGE,
        translation_key="c_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.DEVICEKW,
        translation_key="device_power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.DEVICEMAXSETA,
        translation_key="device_max_set_a",
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ELECTRIC_TOTAL,
        translation_key="electric_total",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.PHASEFLAG,
        translation_key="phaseflag",
    ),
    XTSensorEntityDescription(
        key=XTDPCode.POWERFACTORA,
        translation_key="powerfactora",
    ),
    XTSensorEntityDescription(
        key=XTDPCode.POWERFACTORB,
        translation_key="powerfactorb",
    ),
    XTSensorEntityDescription(
        key=XTDPCode.POWERFACTORC,
        translation_key="powerfactorc",
    ),
    XTSensorEntityDescription(
        key=XTDPCode.POWER_TOTAL,
        translation_key="power_total",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.PV1_VOLT,
        translation_key="pv1_volt",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.PV2_VOLT,
        translation_key="pv2_volt",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.PVV,
        translation_key="pvv",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.PV1_CURR,
        translation_key="pv1_curr",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.PV2_CURR,
        translation_key="pv2_curr",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.PVI,
        translation_key="pvi",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.REACTIVEPOWER,
        translation_key="reactivepower",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.REACTIVE_POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.REACTIVEPOWERA,
        translation_key="reactivepowera",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.REACTIVE_POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.REACTIVEPOWERB,
        translation_key="reactivepowerb",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.REACTIVE_POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.REACTIVEPOWERC,
        translation_key="reactivepowerc",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.REACTIVE_POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.SIGLE_PHASE_POWER,
        translation_key="sigle_phase_power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.VOL_YD,
        translation_key="voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.VOLTAGEA,
        translation_key="a_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.VOLTAGEB,
        translation_key="b_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.VOLTAGEC,
        translation_key="c_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.VOLTAGE_CURRENT,
        translation_key="voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
)

TIMER_SENSORS: tuple[XTSensorEntityDescription, ...] = (
    XTSensorEntityDescription(
        key=XTDPCode.CTIME,
        translation_key="ctime",
        entity_registry_enabled_default=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CTIME2,
        translation_key="ctime2",
        entity_registry_enabled_default=True,
        entity_registry_visible_default=False,
    ),
)

LOCK_SENSORS: tuple[XTSensorEntityDescription, ...] = (
    XTSensorEntityDescription(
        key=XTDPCode.UNLOCK_FINGERPRINT,
        translation_key="unlock_fingerprint",
        entity_registry_enabled_default=True,
        reset_after_x_seconds=2,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.UNLOCK_PASSWORD,
        translation_key="unlock_password",
        entity_registry_enabled_default=True,
        reset_after_x_seconds=2,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.UNLOCK_CARD,
        translation_key="unlock_card",
        entity_registry_enabled_default=True,
        reset_after_x_seconds=2,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.UNLOCK_FACE,
        translation_key="unlock_face",
        entity_registry_enabled_default=True,
        reset_after_x_seconds=2,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.UNLOCK_HAND,
        translation_key="unlock_hand",
        entity_registry_enabled_default=True,
        reset_after_x_seconds=2,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.UNLOCK_FINGER_VEIN,
        translation_key="unlock_finger_vein",
        entity_registry_enabled_default=True,
        reset_after_x_seconds=2,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CLOSED_OPENED,
        translation_key="jtmspro_closed_opened",
        entity_registry_enabled_default=True,
    ),
)

# All descriptions can be found here. Mostly the Integer data types in the
# default status set of each category (that don't have a set instruction)
# end up being a sensor.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
SENSORS: dict[str, tuple[XTSensorEntityDescription, ...]] = {
    CROSS_CATEGORY_DEVICE_DESCRIPTOR: (
        XTSensorEntityDescription(
            key=XTDPCode.XT_COVER_INVERT_CONTROL,
            translation_key="xt_cover_invert_control",
            entity_registry_visible_default=False,
            restoredata=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.XT_COVER_INVERT_STATUS,
            translation_key="xt_cover_invert_status",
            entity_registry_visible_default=False,
            restoredata=True,
            refresh_device_after_load=True,
        ),
    ),
    "cl": (*BATTERY_SENSORS,),
    "dbl": (
        XTSensorEntityDescription(
            key=XTDPCode.COUNTDOWN_LEFT,
            translation_key="countdown_left",
            entity_registry_enabled_default=False,
        ),
    ),
    "hps": (
        XTSensorEntityDescription(
            key=XTDPCode.PRESENCE_STATE,
            translation_key="hps_presence_state",
        ),
        XTSensorEntityDescription(
            key=XTDPCode.TARGET_DISTANCE,
            translation_key="target_distance",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.LDR,
            translation_key="ldr",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.ILLUMINANCE_VALUE,
            translation_key="illuminance_value",
            device_class=SensorDeviceClass.ILLUMINANCE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
    ),
    "pir": (
        XTSensorEntityDescription(
            key=XTDPCode.ILLUMINANCE_VALUE,
            translation_key="illuminance_value",
            device_class=SensorDeviceClass.ILLUMINANCE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
    ),
    "jtmspro": (
        XTSensorEntityDescription(
            key=XTDPCode.ALARM_LOCK,
            translation_key="jtmspro_alarm_lock",
            entity_registry_enabled_default=False,
        ),
        *LOCK_SENSORS,
        *ELECTRICITY_SENSORS,
        *BATTERY_SENSORS,
    ),
    # Switch
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
    "kg": (
        XTSensorEntityDescription(
            key=XTDPCode.ILLUMINANCE_VALUE,
            translation_key="illuminance_value",
            device_class=SensorDeviceClass.ILLUMINANCE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.METER_TYPE,
            translation_key="meter_type",
        ),
        XTSensorEntityDescription(
            key=XTDPCode.FREQUENCY,
            translation_key="frequency",
            device_class=SensorDeviceClass.FREQUENCY,
        ),
        *TEMPERATURE_SENSORS,
        *HUMIDITY_SENSORS,
        *CONSUMPTION_SENSORS,
        *ELECTRICITY_SENSORS,
    ),
    "MPPT": (
        XTSensorEntityDescription(
            key=XTDPCode.PRODUCT_SPECIFICATIONS,
            translation_key="product_specifications",
        ),
        XTSensorEntityDescription(
            key=XTDPCode.DEVICEID,
            translation_key="deviceid",
        ),
        XTSensorEntityDescription(
            key=XTDPCode.RELEASES,
            translation_key="releases",
        ),
        *TEMPERATURE_SENSORS,
        *ELECTRICITY_SENSORS,
        *CONSUMPTION_SENSORS,
    ),
    "ms": (
        *BATTERY_SENSORS,
        *LOCK_SENSORS,
    ),
    # Automatic cat litter box
    # Note: Undocumented
    "msp": (
        XTSensorEntityDescription(
            key=XTDPCode.AUTO_DEORDRIZER,
            translation_key="auto_deordrizer",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.CALIBRATION,
            translation_key="calibration",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.CAPACITY_CALIBRATION,
            translation_key="capacity_calibration",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.CAT_WEIGHT,
            translation_key="cat_weight",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.CLEAN_NOTICE,
            translation_key="clean_notice",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.CLEAN_TASTE,
            translation_key="clean_taste",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.CLEAN_TIME,
            translation_key="clean_time",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.DEODORIZATION_NUM,
            translation_key="ozone_concentration",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.DETECTION_SENSITIVITY,
            translation_key="detection_sensitivity",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.EXCRETION_TIMES_DAY,
            translation_key="excretion_times_day",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.EXCRETION_TIME_DAY,
            translation_key="excretion_time_day",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.HISTORY,
            translation_key="msp_history",
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.INDUCTION_CLEAN,
            translation_key="induction_clean",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.INDUCTION_DELAY,
            translation_key="induction_delay",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.INDUCTION_INTERVAL,
            translation_key="induction_interval",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.MONITORING,
            translation_key="monitoring",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.NET_NOTICE,
            translation_key="net_notice",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.NOT_DISTURB,
            translation_key="not_disturb",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.NOTIFICATION_STATUS,
            translation_key="notification_status",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.NUMBER,
            translation_key="number",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.ODOURLESS,
            translation_key="odourless",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.PEDAL_ANGLE,
            translation_key="pedal_angle",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.PIR_RADAR,
            translation_key="pir_radar",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.SAND_SURFACE_CALIBRATION,
            translation_key="sand_surface_calibration",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.SMART_CLEAN,
            translation_key="smart_clean",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.STORE_FULL_NOTIFY,
            translation_key="store_full_notify",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.TOILET_NOTICE,
            translation_key="toilet_notice",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.UNIT,
            translation_key="unit",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.USAGE_TIMES,
            translation_key="usage_times",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.WORK_STAT,
            translation_key="work_stat",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        *TEMPERATURE_SENSORS,
    ),
    "ms_category": (
        XTSensorEntityDescription(
            key=XTDPCode.ALARM_LOCK,
            translation_key="ms_category_alarm_lock",
            entity_registry_enabled_default=False,
            reset_after_x_seconds=1,
        ),
        *LOCK_SENSORS,
        *BATTERY_SENSORS,
    ),
    "mzj": (
        XTSensorEntityDescription(
            key=XTDPCode.WORK_STATUS,
            translation_key="mzj_work_status",
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.REMAININGTIME,
            translation_key="remaining_time",
            entity_registry_enabled_default=True,
        ),
        *TEMPERATURE_SENSORS,
    ),
    "qccdz": (
        XTSensorEntityDescription(
            key=XTDPCode.WORK_STATE,
            translation_key="qccdz_work_state",
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.CONNECTION_STATE,
            translation_key="qccdz_connection_state",
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.SYSTEM_VERSION,
            translation_key="system_version",
            entity_registry_enabled_default=True,
            entity_registry_visible_default=False,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.DEVICESTATE,
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
            key=XTDPCode.WATER_ONCE,
            translation_key="water_once",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.WATER_TOTAL,
            translation_key="water_total",
            state_class=SensorStateClass.TOTAL_INCREASING,
            entity_registry_enabled_default=True,
        ),
    ),
    "slj": (
        XTSensorEntityDescription(
            key=XTDPCode.WATER_USE_DATA,
            translation_key="water_use_data",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.WATER_ONCE,
            translation_key="water_once",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.FLOW_VELOCITY,
            translation_key="flow_velocity",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        *ELECTRICITY_SENSORS,
    ),
    "smd": (
        XTSensorEntityDescription(
            key=XTDPCode.HEART_RATE,
            translation_key="heart_rate",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.RESPIRATORY_RATE,
            translation_key="respiratory_rate",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.SLEEP_STAGE,
            translation_key="sleep_stage",
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.TIME_GET_IN_BED,
            translation_key="time_get_in_bed",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.OFF_BED_TIME,
            translation_key="off_bed_time",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.CLCT_TIME,
            translation_key="clct_time",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
    ),
    "wk": (
        *BATTERY_SENSORS,
        *TEMPERATURE_SENSORS,
    ),
    "wnykq": (
        XTSensorEntityDescription(
            key=XTDPCode.IR_CONTROL,
            translation_key="wnykq_ir_control",
            entity_registry_enabled_default=True,
        ),
        *TEMPERATURE_SENSORS,
        *HUMIDITY_SENSORS,
    ),
    "wsdcg": (
        *TEMPERATURE_SENSORS,
        *HUMIDITY_SENSORS,
        *BATTERY_SENSORS,
    ),
    "xfj": (
        XTSensorEntityDescription(
            key=XTDPCode.PM25,
            translation_key="pm25",
            device_class=SensorDeviceClass.PM25,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.ECO2,
            translation_key="concentration_carbon_dioxide",
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.FILTER_LIFE,
            translation_key="filter_life",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.TVOC,
            translation_key="tvoc",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.AIR_QUALITY,
            translation_key="air_quality",
        ),
        *TEMPERATURE_SENSORS,
        *HUMIDITY_SENSORS,
    ),
    "ywcgq": (
        XTSensorEntityDescription(
            key=XTDPCode.LIQUID_STATE,
            translation_key="liquid_state",
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.LIQUID_DEPTH,
            translation_key="liquid_depth",
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.LIQUID_LEVEL_PERCENT,
            translation_key="liquid_level_percent",
            entity_registry_enabled_default=True,
            recalculate_scale_for_percentage=True,
            recalculate_scale_for_percentage_threshold=1000,
        ),
    ),
    # ZNRB devices don't send correct cloud data, for these devices use https://github.com/make-all/tuya-local instead
    # "znrb": (
    #    *CONSUMPTION_SENSORS,
    #    *TEMPERATURE_SENSORS,
    # ),
    "zwjcy": (
        *TEMPERATURE_SENSORS,
        *HUMIDITY_SENSORS,
        *BATTERY_SENSORS,
    ),
}

# Socket (duplicate of `kg`)
# https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
SENSORS["cz"] = SENSORS["kg"]
SENSORS["wkcz"] = SENSORS["kg"]
SENSORS["dlq"] = SENSORS["kg"]
SENSORS["tdq"] = SENSORS["kg"]
SENSORS["pc"] = SENSORS["kg"]
SENSORS["aqcz"] = SENSORS["kg"]
SENSORS["zndb"] = SENSORS["kg"]

# Lock duplicates
SENSORS["videolock"] = SENSORS["jtmspro"]
SENSORS["jtmsbh"] = SENSORS["jtmspro"]


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya sensor dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, tuple[XTSensorEntityDescription, ...]],
            dict[str, tuple[XTSensorEntityDescription, ...]],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            SENSORS, entry.runtime_data.multi_manager, Platform.SENSOR
        ),
    )

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered Tuya sensor."""
        if hass_data.manager is None:
            return
        entities: list[XTSensorEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if category_descriptions := XTEntityDescriptorManager.get_category_descriptors(supported_descriptors, device.category):
                    externally_managed_dpcodes = (
                        XTEntityDescriptorManager.get_category_keys(
                            externally_managed_descriptors.get(device.category)
                        )
                    )
                    if restrict_dpcode is not None:
                        category_descriptions = cast(
                            tuple[XTSensorEntityDescription, ...],
                            restrict_descriptor_category(
                                category_descriptions, [restrict_dpcode]
                            ),
                        )
                    entities.extend(
                        XTSensorEntity.get_entity_instance(
                            description, device, hass_data.manager
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device, description, True, externally_managed_dpcodes
                        )
                    )
                    entities.extend(
                        XTSensorEntity.get_entity_instance(
                            description, device, hass_data.manager
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device, description, False, externally_managed_dpcodes
                        )
                    )

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors(Platform.SENSOR, supported_descriptors)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTSensorEntity(XTEntity, TuyaSensorEntity, RestoreSensor):  # type: ignore
    """XT Sensor Entity."""

    entity_description: XTSensorEntityDescription
    _restored_data: SensorExtraStoredData | None = None
    cancel_reset_after_x_seconds: CALLBACK_TYPE | None = None

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

        if int_type := self.find_dpcode(description.key, dptype=TuyaDPType.INTEGER):
            self._type_data = int_type
            self._type = TuyaDPType.INTEGER
            if description.native_unit_of_measurement is None:
                self._attr_native_unit_of_measurement = int_type.unit
        elif enum_type := self.find_dpcode(
            description.key, dptype=TuyaDPType.ENUM, prefer_function=True
        ):
            self._type_data = enum_type
            self._type = TuyaDPType.ENUM
        else:
            self._type = self.get_dptype(description.key)  # type: ignore #This is modified from TuyaSensorEntity's constructor

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

        if description.recalculate_scale_for_percentage:
            device_manager.execute_device_entity_function(
                XTDeviceEntityFunctions.RECALCULATE_PERCENT_SCALE,
                device,
                description.key,
                description.recalculate_scale_for_percentage_threshold,
            )

        """Init XT sensor."""
        super(XTSensorEntity, self).__init__(device, device_manager, description)
        try:
            super(XTEntity, self).__init__(device, device_manager, description)  # type: ignore
        except Exception:
            self._replaced_constructor(
                device=device, device_manager=device_manager, description=description
            )

        self.device = device
        self.device_manager = device_manager
        self.entity_description = description  # type: ignore
        self.cancel_reset_after_x_seconds = None

    def reset_value(
        self, _: datetime.datetime | None, manual_call: bool = False
    ) -> None:
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
                        self.async_write_ha_state()

        if (
            self.entity_description.reset_daily
            or self.entity_description.reset_monthly
            or self.entity_description.reset_yearly
        ):
            self.async_on_remove(
                async_track_time_change(
                    self.hass, reset_status_daily, hour=0, minute=0, second=0
                )
            )
        if self.entity_description.reset_after_x_seconds:
            self.reset_value(None, True)
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    self.entity_id,
                    self._on_state_change_event,
                )
            )

        if self.entity_description.restoredata:
            self._restored_data = await self.async_get_last_sensor_data()
            if (
                self._restored_data is not None
                and self._restored_data.native_value is not None
            ):
                # Scale integer/float value
                if isinstance(self._type_data, TuyaIntegerTypeData):
                    scaled_value_back = self._type_data.scale_value_back(self._restored_data.native_value)  # type: ignore
                    self._restored_data.native_value = scaled_value_back

                if device := self.device_manager.device_map.get(self.device.id, None):
                    device.status[self.entity_description.key] = (
                        self._restored_data.native_value
                    )

        if self.entity_description.refresh_device_after_load:
            self.device_manager.multi_device_listener.update_device(
                self.device, [self.entity_description.key]
            )

    @callback
    async def _on_state_change_event(self, event: Event[EventStateChangedData]):
        new_state: State | None = event.data.get("new_state")
        default_value = get_default_value(self._type)
        if new_state is None or not new_state.state or new_state.state == default_value:
            return
        if self.cancel_reset_after_x_seconds:
            self.cancel_reset_after_x_seconds()
        self.cancel_reset_after_x_seconds = async_call_later(
            self.hass, self.entity_description.reset_after_x_seconds, self.reset_value
        )

    @staticmethod
    def get_entity_instance(
        description: XTSensorEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
    ) -> XTSensorEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(device, device_manager, description)
        return XTSensorEntity(
            device, device_manager, XTSensorEntityDescription(**description.__dict__)
        )
