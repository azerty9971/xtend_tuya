"""Support for Tuya sensors."""

from __future__ import annotations

from dataclasses import dataclass

from tuya_sharing import CustomerDevice, Manager
from tuya_sharing.device import DeviceStatusRange

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    RestoreSensor,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTime,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import TuyaConfigEntry
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


@dataclass(frozen=True)
class TuyaSensorEntityDescription(SensorEntityDescription):
    """Describes Tuya sensor entity."""

    subkey: str | None = None

    virtualstate: VirtualStates | None = None

    restoredata: bool = False

# Commonly used battery sensors, that are re-used in the sensors down below.
BATTERY_SENSORS: tuple[TuyaSensorEntityDescription, ...] = (
)

# All descriptions can be found here. Mostly the Integer data types in the
# default status set of each category (that don't have a set instruction)
# end up being a sensor.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
SENSORS: dict[str, tuple[TuyaSensorEntityDescription, ...]] = {
    # Switch
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
    "kg": (
        TuyaSensorEntityDescription(
            key=DPCode.ADD_ELE,
            virtualstate=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
            translation_key="add_ele",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            entity_registry_enabled_default=True,
            restoredata=True,
        ),
    ),
    # IoT Switch
    # Note: Undocumented
    "tdq": (
        TuyaSensorEntityDescription(
            key=DPCode.ADD_ELE,
            #virtualstate=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
            translation_key="add_ele",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            entity_registry_enabled_default=True,
            restoredata=True,
        ),
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
            key=DPCode.CLEAN,
            translation_key="clean",
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
            key=DPCode.DEODORIZATION,
            translation_key="deodorization",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        TuyaSensorEntityDescription(
            key=DPCode.DEODORIZATION_NUM,
            translation_key="deodorization_num",
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
            key=DPCode.EMPTY,
            translation_key="empty",
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
            key=DPCode.MAGNETNUM,
            translation_key="magnetnum",
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
            entity_registry_enabled_default=True,
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
            key=DPCode.TEMPERATURE,
            translation_key="temperature",
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
    ),
}

# Socket (duplicate of `kg`)
# https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
SENSORS["cz"] = SENSORS["kg"]
SENSORS["wkcz"] = SENSORS["kg"]
SENSORS["dlq"] = SENSORS["kg"]

# Power Socket (duplicate of `kg`)
# https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
SENSORS["pc"] = SENSORS["kg"]

async def async_setup_entry(
    hass: HomeAssistant, entry: TuyaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya sensor dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    @callback
    def async_discover_device(manager, device_map) -> None:
        """Discover and add a discovered Tuya sensor."""
        entities: list[TuyaSensorEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            device = device_map[device_id]
            if descriptions := SENSORS.get(device.category):
                entities.extend(
                    TuyaSensorEntity(device, manager, description)
                    for description in descriptions
                    if description.key in device.status
                )

        async_add_entities(entities)

    async_discover_device(hass_data.manager, hass_data.manager.device_map)
    async_discover_device(hass_data.manager, hass_data.manager.open_api_device_map)

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
        device_manager: Manager,
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
        if not self.entity_description.restoredata:
            return
        state = await self.async_get_last_sensor_data()
        if state is None:
            return
        # Scale integer/float value
        if isinstance(self._type_data, IntegerTypeData):
            scaled_value_back = self._type_data.scale_value_back(state.native_value)
            state.native_value = scaled_value_back
        if state:
            self.device.status[self.entity_description.key] = float(state.native_value)
