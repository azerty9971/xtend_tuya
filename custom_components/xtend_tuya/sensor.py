"""Support for Tuya sensors."""

from __future__ import annotations

import datetime

from dataclasses import dataclass, field

from tuya_sharing import CustomerDevice
from tuya_sharing.device import DeviceStatusRange

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
    RestoreSensor,
)
from homeassistant.const import (
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.event import async_track_time_change

try:
    from custom_components.tuya.sensor import ( # type: ignore
        SENSORS as SENSORS_TUYA
    )
except ImportError:
    from homeassistant.components.tuya.sensor import (
        SENSORS as SENSORS_TUYA
    )
from .util import (
    merge_device_descriptors
)

from .multi_manager import XTConfigEntry, MultiManager
from .base import ElectricityTypeData, EnumTypeData, IntegerTypeData, TuyaEntity
from .const import (
    DEVICE_CLASS_UNITS,
    DOMAIN,
    TUYA_DISCOVERY_NEW,
    DPCode,
    DPType,
    UnitOfMeasurement,
    VirtualStates,
)


@dataclass
class TuyaSensorEntityDescription(SensorEntityDescription):
    """Describes Tuya sensor entity."""

    subkey: str | None = None

    virtual_state: VirtualStates | None = None
    vs_copy_to_state: list[DPCode]  | None = field(default_factory=list)

    reset_daily: bool = False
    reset_monthly: bool = False
    reset_yearly: bool = False
    restoredata: bool = False

# Commonly used battery sensors, that are re-used in the sensors down below.
BATTERY_SENSORS: tuple[TuyaSensorEntityDescription, ...] = (
)

#Commonlu sed energy sensors, that are re-used in the sensors down below.
CONSUMPTION_SENSORS: tuple[TuyaSensorEntityDescription, ...] = (
    TuyaSensorEntityDescription(
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
    TuyaSensorEntityDescription(
        key=DPCode.ADD_ELE2,
        translation_key="add_ele2",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
    ),
    TuyaSensorEntityDescription(
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
    TuyaSensorEntityDescription(
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
    TuyaSensorEntityDescription(
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
    TuyaSensorEntityDescription(
        key=DPCode.BALANCE_ENERGY,
        translation_key="balance_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=False,
    ),
    TuyaSensorEntityDescription(
        key=DPCode.CHARGE_ENERGY,
        translation_key="charge_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=False,
    ),
    TuyaSensorEntityDescription(
        key=DPCode.TOTAL_FORWARD_ENERGY,
        translation_key="total_forward_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=False,
    ),
    TuyaSensorEntityDescription(
        key=DPCode.CUR_POWER,
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
)

TEMPERATURE_SENSORS: tuple[TuyaSensorEntityDescription, ...] = (
    TuyaSensorEntityDescription(
        key=DPCode.TEMPERATURE,
        translation_key="temperature",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
    TuyaSensorEntityDescription(
        key=DPCode.TEMP_CURRENT,
        translation_key="temperature",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
    TuyaSensorEntityDescription(
        key=DPCode.TEMP_VALUE,
        translation_key="temperature",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
)

HUMIDITY_SENSORS: tuple[TuyaSensorEntityDescription, ...] = (
    TuyaSensorEntityDescription(
        key=DPCode.HUMIDITY_VALUE,
        translation_key="humidity",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
)

# All descriptions can be found here. Mostly the Integer data types in the
# default status set of each category (that don't have a set instruction)
# end up being a sensor.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
SENSORS: dict[str, tuple[TuyaSensorEntityDescription, ...]] = {
    # Switch
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
    "kg": (
        *CONSUMPTION_SENSORS,
    ),
    # Automatic cat litter box
    # Note: Undocumented
    "msp": (
        TuyaSensorEntityDescription(
            key=DPCode.AUTO_DEORDRIZER,
            translation_key="auto_deordrizer",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CALIBRATION,
            translation_key="calibration",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CAPACITY_CALIBRATION,
            translation_key="capacity_calibration",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CAT_WEIGHT,
            translation_key="cat_weight",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CLEAN_NOTICE,
            translation_key="clean_notice",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CLEAN_TASTE,
            translation_key="clean_taste",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CLEAN_TIME,
            translation_key="clean_time",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.DEODORIZATION_NUM,
            translation_key="ozone_concentration",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.DETECTION_SENSITIVITY,
            translation_key="detection_sensitivity",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.EXCRETION_TIMES_DAY,
            translation_key="excretion_times_day",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.EXCRETION_TIME_DAY,
            translation_key="excretion_time_day",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.HISTORY,
            translation_key="msp_history",
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.INDUCTION_CLEAN,
            translation_key="induction_clean",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.INDUCTION_DELAY,
            translation_key="induction_delay",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.INDUCTION_INTERVAL,
            translation_key="induction_interval",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.MONITORING,
            translation_key="monitoring",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.NET_NOTICE,
            translation_key="net_notice",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.NOT_DISTURB,
            translation_key="not_disturb",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.NOTIFICATION_STATUS,
            translation_key="notification_status",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.NUMBER,
            translation_key="number",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.ODOURLESS,
            translation_key="odourless",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PEDAL_ANGLE,
            translation_key="pedal_angle",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.PIR_RADAR,
            translation_key="pir_radar",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.SAND_SURFACE_CALIBRATION,
            translation_key="sand_surface_calibration",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.SMART_CLEAN,
            translation_key="smart_clean",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.STORE_FULL_NOTIFY,
            translation_key="store_full_notify",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TOILET_NOTICE,
            translation_key="toilet_notice",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.UNIT,
            translation_key="unit",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.USAGE_TIMES,
            translation_key="usage_times",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.WORK_STAT,
            translation_key="work_stat",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        *TEMPERATURE_SENSORS,
    ),
    "smd": (
        TuyaSensorEntityDescription(
            key=DPCode.HEART_RATE,
            translation_key="heart_rate",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.RESPIRATORY_RATE,
            translation_key="respiratory_rate",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.SLEEP_STAGE,
            translation_key="sleep_stage",
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.TIME_GET_IN_BED,
            translation_key="time_get_in_bed",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.OFF_BED_TIME,
            translation_key="off_bed_time",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.CLCT_TIME,
            translation_key="clct_time",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
    ),
    "wnykq": (
        TuyaSensorEntityDescription(
            key=DPCode.IR_CONTROL,
            translation_key="wnykq_ir_control",
            entity_registry_enabled_default=True,
        ),
        *TEMPERATURE_SENSORS,
        *HUMIDITY_SENSORS,
    ),
    "ywcgq": (
        TuyaSensorEntityDescription(
            key=DPCode.LIQUID_STATE,
            translation_key="liquid_state",
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.LIQUID_DEPTH,
            translation_key="liquid_depth",
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.LIQUID_LEVEL_PERCENT,
            translation_key="liquid_level_percent",
            entity_registry_enabled_default=True,
        ),
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

async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya sensor dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    merged_descriptors = SENSORS
    if not entry.runtime_data.multi_manager.reuse_config:
        merged_descriptors = merge_device_descriptors(SENSORS, SENSORS_TUYA)

    @callback
    def async_discover_device(device_map) -> None:
        """Discover and add a discovered Tuya sensor."""
        entities: list[TuyaSensorEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if descriptions := merged_descriptors.get(device.category):
                    entities.extend(
                        TuyaSensorEntity(device, hass_data.manager, description)
                        for description in descriptions
                        if description.key in device.status
                    )

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors("sensors", merged_descriptors)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaSensorEntity(TuyaEntity, RestoreSensor):
    """Tuya Sensor Entity."""

    entity_description: TuyaSensorEntityDescription

    _status_range: DeviceStatusRange | None = None
    _type: DPType | None = None
    _type_data: IntegerTypeData | EnumTypeData | None = None
    _uom: UnitOfMeasurement | None = None

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: MultiManager,
        description: TuyaSensorEntityDescription,
    ) -> None:
        """Init Tuya sensor."""
        super().__init__(device, device_manager)
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
            self._type = self.get_dptype(DPCode(description.key))

        # Logic to ensure the set device class and API received Unit Of Measurement
        # match Home Assistants requirements.
        if (
            self.device_class is not None
            and not self.device_class.startswith(DOMAIN)
            and description.native_unit_of_measurement is None
        ):
            # We cannot have a device class, if the UOM isn't set or the
            # device class cannot be found in the validation mapping.
            if (
                self.native_unit_of_measurement is None
                or self.device_class not in DEVICE_CLASS_UNITS
            ):
                self._attr_device_class = None
                return

            uoms = DEVICE_CLASS_UNITS[self.device_class]
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

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        # Only continue if data type is known
        if self._type not in (
            DPType.INTEGER,
            DPType.STRING,
            DPType.ENUM,
            DPType.JSON,
            DPType.RAW,
        ):
            return None

        # Raw value
        value = self.device.status.get(self.entity_description.key)
        if value is None:
            return None

        # Scale integer/float value
        if isinstance(self._type_data, IntegerTypeData):
            scaled_value = self._type_data.scale_value(value)
            if self._uom and self._uom.conversion_fn is not None:
                return self._uom.conversion_fn(scaled_value)
            return scaled_value

        # Unexpected enum value
        if (
            isinstance(self._type_data, EnumTypeData)
            and value not in self._type_data.range
        ):
            return None

        # Get subkey value from Json string.
        if self._type is DPType.JSON:
            if self.entity_description.subkey is None:
                return None
            values = ElectricityTypeData.from_json(value)
            return getattr(values, self.entity_description.subkey)

        if self._type is DPType.RAW:
            if self.entity_description.subkey is None:
                return None
            values = ElectricityTypeData.from_raw(value)
            return getattr(values, self.entity_description.subkey)

        # Valid string or enum value
        return value
    
    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        async def reset_status_daily(now: datetime.datetime) -> None:
            should_reset = False
            if hasattr(self.entity_description, "reset_daily") and self.entity_description.reset_daily:
                should_reset = True

            if hasattr(self.entity_description, "reset_monthly") and self.entity_description.reset_monthly and now.day == 1:
                should_reset = True

            if hasattr(self.entity_description, "reset_yearly") and self.entity_description.reset_yearly and now.day == 1 and now.month == 1:
                should_reset = True
            
            if should_reset:
                devices = self.device_manager.get_devices_from_device_id(self.device.id)
                for device in devices:
                    device.status[self.entity_description.key] = float(0)
                self.entity_description.last_reset = now

        if (
           ( hasattr(self.entity_description, "reset_daily") and self.entity_description.reset_daily )
        or ( hasattr(self.entity_description, "reset_monthly") and self.entity_description.reset_monthly )
        or ( hasattr(self.entity_description, "reset_yearly") and self.entity_description.reset_yearly )
        ):
            self.async_on_remove(
                async_track_time_change(
                    self.hass, reset_status_daily, hour=18, minute=47, second=0
                )
            )

        if not hasattr(self.entity_description, "restoredata") or not self.entity_description.restoredata:
            return
        state = await self.async_get_last_sensor_data()
        if state is None or state.native_value is None:
            return
        # Scale integer/float value
        if isinstance(self._type_data, IntegerTypeData):
            scaled_value_back = self._type_data.scale_value_back(state.native_value)
            state.native_value = scaled_value_back

        devices = self.device_manager.get_devices_from_device_id(self.device.id)
        for device in devices:
            device.status[self.entity_description.key] = float(state.native_value)
