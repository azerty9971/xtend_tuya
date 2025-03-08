"""Support for XT binary sensors."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
)
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .util import (
    merge_device_descriptors
)

from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .const import TUYA_DISCOVERY_NEW, DPCode, LOGGER
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaBinarySensorEntity,
    TuyaBinarySensorEntityDescription,
)
from .entity import (
    XTEntity,
)

@dataclass(frozen=True)
class XTBinarySensorEntityDescription(TuyaBinarySensorEntityDescription):
    """Describes an XT binary sensor."""

    # This DPCode represent the online status of a device
    device_online: bool = False

    """ def __init__(self, *args, **kwargs):
        super(XTBinarySensorEntityDescription, self).__init__(*args, **kwargs) """


# Commonly used sensors
TAMPER_BINARY_SENSOR = XTBinarySensorEntityDescription(
    key=DPCode.TEMPER_ALARM,
    name="Tamper",
    device_class=BinarySensorDeviceClass.TAMPER,
    entity_category=EntityCategory.DIAGNOSTIC,
)


# All descriptions can be found here. Mostly the Boolean data types in the
# default status set of each category (that don't have a set instruction)
# end up being a binary sensor.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
BINARY_SENSORS: dict[str, tuple[XTBinarySensorEntityDescription, ...]] = {
    "jtmspro": (
        XTBinarySensorEntityDescription(
            key=DPCode.LOCK_MOTOR_STATE,
            translation_key="lock_motor_state",
            device_class=BinarySensorDeviceClass.LOCK,
            on_value=True
        ),
    ),
    "kg": (
        XTBinarySensorEntityDescription(
            key=DPCode.PRESENCE_STATE,
            device_class=BinarySensorDeviceClass.MOTION,
            on_value="presence",
        ),
    ),
    "msp": (
        #If 1 is reported, it will be counted once. 
        #If 0 is reported, it will not be counted
        #(today and the average number of toilet visits will be counted on the APP)
        XTBinarySensorEntityDescription(
            key=DPCode.CLEANING_NUM,
            translation_key="cleaning_num",
        ),
        XTBinarySensorEntityDescription(
            key=DPCode.TRASH_STATUS,
            translation_key="trash_status",
            entity_registry_enabled_default=True,
            on_value="1",
        ),
        XTBinarySensorEntityDescription(
            key=DPCode.POWER,
            translation_key="power",
            entity_registry_enabled_default=False,
        ),
    ),
    "pir": (
        XTBinarySensorEntityDescription(
            key=DPCode.PIR2,
            device_class=BinarySensorDeviceClass.MOTION,
        ),
    ),
    #"qccdz": (
    #    XTBinarySensorEntityDescription(
    #        key=DPCode.ONLINE_STATE,
    #        translation_key="online",
    #        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    #        entity_registry_visible_default=False,
    #        device_online=True,
    #        on_value="online",
    #    ),
    #),
    "smd": (
        XTBinarySensorEntityDescription(
            key=DPCode.OFF_BED,
            translation_key="off_bed",
        ),
        XTBinarySensorEntityDescription(
            key=DPCode.WAKEUP,
            translation_key="wakeup",
        ),
        XTBinarySensorEntityDescription(
            key=DPCode.OFF,
            translation_key="off",
        ),
    ),
}

#Lock duplicates
BINARY_SENSORS["videolock"] = BINARY_SENSORS["jtmspro"]

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
        entities: list[XTBinarySensorEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id, None):
                if descriptions := merged_descriptors.get(device.category):
                    for description in descriptions:
                        dpcode = description.dpcode or description.key
                        if dpcode in device.status:
                            entities.append(
                                XTBinarySensorEntity(
                                    device, hass_data.manager, XTBinarySensorEntityDescription(**description.__dict__)
                                )
                            )

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors("binary_sensors", merged_descriptors)
    async_discover_device([*hass_data.manager.device_map])
    #async_discover_device(hass_data.manager, hass_data.manager.open_api_device_map)

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTBinarySensorEntity(XTEntity, TuyaBinarySensorEntity):
    """XT Binary Sensor Entity."""

    entity_description: XTBinarySensorEntityDescription

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTBinarySensorEntityDescription,
    ) -> None:
        """Init Tuya binary sensor."""
        super(XTBinarySensorEntity, self).__init__(device, device_manager, description)
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        is_on = super().is_on
        if self.entity_description.device_online:
            dpcode = self.entity_description.dpcode or self.entity_description.key
            self.device.online_states[dpcode] = is_on
            self.device_manager.update_device_online_status(self.device.id)
        return is_on
    
    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()
        self.is_on #Update the online status if needed