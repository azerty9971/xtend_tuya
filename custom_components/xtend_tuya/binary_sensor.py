"""Support for Tuya binary sensors."""

from __future__ import annotations

from dataclasses import dataclass

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .util import (
    merge_device_descriptors
)

from .multi_manager.multi_manager import XTConfigEntry
from .base import TuyaEntity
from .const import TUYA_DISCOVERY_NEW, DPCode


@dataclass(frozen=True)
class TuyaBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Tuya binary sensor."""

    # DPCode, to use. If None, the key will be used as DPCode
    dpcode: DPCode | None = None

    # Value or values to consider binary sensor to be "on"
    on_value: bool | float | int | str | set[bool | float | int | str] = True

    # This DPCode represent the online status of a device
    device_online: bool = False


# Commonly used sensors
TAMPER_BINARY_SENSOR = TuyaBinarySensorEntityDescription(
    key=DPCode.TEMPER_ALARM,
    name="Tamper",
    device_class=BinarySensorDeviceClass.TAMPER,
    entity_category=EntityCategory.DIAGNOSTIC,
)


# All descriptions can be found here. Mostly the Boolean data types in the
# default status set of each category (that don't have a set instruction)
# end up being a binary sensor.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
BINARY_SENSORS: dict[str, tuple[TuyaBinarySensorEntityDescription, ...]] = {
    "jtmspro": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.LOCK_MOTOR_STATE,
            translation_key="lock_motor_state",
            device_class=BinarySensorDeviceClass.LOCK,
            on_value=True
        ),
    ),
    "kg": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.PRESENCE_STATE,
            device_class=BinarySensorDeviceClass.MOTION,
            on_value="presence",
        ),
    ),
    "msp": (
        #If 1 is reported, it will be counted once. 
        #If 0 is reported, it will not be counted
        #(today and the average number of toilet visits will be counted on the APP)
        TuyaBinarySensorEntityDescription(
            key=DPCode.CLEANING_NUM,
            translation_key="cleaning_num",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.TRASH_STATUS,
            translation_key="trash_status",
            entity_registry_enabled_default=True,
            on_value="1",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.POWER,
            translation_key="power",
            entity_registry_enabled_default=False,
        ),
    ),
    "pir": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.PIR2,
            device_class=BinarySensorDeviceClass.MOTION,
        ),
    ),
    "smd": (
        TuyaBinarySensorEntityDescription(
            key=DPCode.OFF_BED,
            translation_key="off_bed",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.WAKEUP,
            translation_key="wakeup",
        ),
        TuyaBinarySensorEntityDescription(
            key=DPCode.OFF,
            translation_key="off",
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya binary sensor dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    merged_descriptors = BINARY_SENSORS
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.BINARY_SENSOR):
        merged_descriptors = merge_device_descriptors(merged_descriptors, new_descriptor)

    @callback
    def async_discover_device(device_map) -> None:
        """Discover and add a discovered Tuya binary sensor."""
        entities: list[TuyaBinarySensorEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id, None):
                if descriptions := merged_descriptors.get(device.category):
                    for description in descriptions:
                        dpcode = description.dpcode or description.key
                        if dpcode in device.status:
                            entities.append(
                                TuyaBinarySensorEntity(
                                    device, hass_data.manager, description
                                )
                            )

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors("binary_sensors", merged_descriptors)
    async_discover_device([*hass_data.manager.device_map])
    #async_discover_device(hass_data.manager, hass_data.manager.open_api_device_map)

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaBinarySensorEntity(TuyaEntity, BinarySensorEntity):
    """Tuya Binary Sensor Entity."""

    entity_description: TuyaBinarySensorEntityDescription

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: TuyaBinarySensorEntityDescription,
    ) -> None:
        """Init Tuya binary sensor."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

    @property
    def is_on(self) -> bool:
        is_on = self._is_on()
        if hasattr(self.entity_description, "device_online") and self.entity_description.device_online:
            self.device.online = is_on
        return is_on
    
    def _is_on(self) -> bool:
        """Return true if sensor is on."""
        dpcode = self.entity_description.dpcode or self.entity_description.key
        if dpcode not in self.device.status:
            return False

        if isinstance(self.entity_description.on_value, set):
            return self.device.status[dpcode] in self.entity_description.on_value

        return self.device.status[dpcode] == self.entity_description.on_value
