"""Support for Tuya sensors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from tuya_sharing import CustomerDevice, Manager
from tuya_sharing.device import DeviceStatusRange

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    RestoreSensor,
)
from homeassistant.config_entries import ConfigEntry
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

from . import HomeAssistantTuyaData
from .base import ElectricityTypeData, EnumTypeData, IntegerTypeData, TuyaEntity
from .const import (
    DEVICE_CLASS_UNITS,
    DOMAIN,
    TUYA_DISCOVERY_NEW,
    LOGGER,
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
            virtualstate=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
            translation_key="add_ele",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            entity_registry_enabled_default=True,
            restoredata=True,
        ),
    ),
}

# Socket (duplicate of `kg`)
# https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
SENSORS["cz"] = SENSORS["kg"]

# Power Socket (duplicate of `kg`)
# https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
SENSORS["pc"] = SENSORS["kg"]

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya sensor dynamically through Tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya sensor."""
        entities: list[TuyaSensorEntity] = []
        for device_id in device_ids:
            device = hass_data.manager.device_map[device_id]
            if descriptions := SENSORS.get(device.category):
                entities.extend(
                    TuyaSensorEntity(device, hass_data.manager, description)
                    for description in descriptions
                    if description.key in device.status
                )

        async_add_entities(entities)

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
        if self.entity_description.restoredata == False:
            return
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()
        state = await self.async_get_last_sensor_data()
        LOGGER.debug("async_added_to_hass: {state}")
        if state:
            self.device.status[self.entity_description.key] = cast(float, state.native_value)
        super().async_added_to_hass()
