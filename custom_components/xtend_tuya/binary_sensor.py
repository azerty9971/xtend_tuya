"""Support for XT binary sensors."""

from __future__ import annotations
from dataclasses import dataclass
from typing import cast
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
)
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .util import (
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
    LOGGER,  # noqa: F401
    CROSS_CATEGORY_DEVICE_DESCRIPTOR,  # noqa: F401
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaBinarySensorEntity,
    TuyaBinarySensorEntityDescription,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)


@dataclass(frozen=True)
class XTBinarySensorEntityDescription(TuyaBinarySensorEntityDescription):
    """Describes an XT binary sensor."""

    # This DPCode represent the online status of a device
    device_online: bool = False

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTBinarySensorEntityDescription,
    ) -> XTBinarySensorEntity:
        return XTBinarySensorEntity(
            device=device, device_manager=device_manager, description=description
        )


# Commonly used sensors
TAMPER_BINARY_SENSOR = XTBinarySensorEntityDescription(
    key=XTDPCode.TEMPER_ALARM,
    name="Tamper",
    device_class=BinarySensorDeviceClass.TAMPER,
    entity_category=EntityCategory.DIAGNOSTIC,
)

PROXIMITY_BINARY_SENSOR: tuple[XTBinarySensorEntityDescription, ...] = (
    XTBinarySensorEntityDescription(
        key=XTDPCode.PRESENCE_STATE,
        translation_key="pir_state",
        device_class=BinarySensorDeviceClass.MOTION,
        on_value="presence",
    ),
    XTBinarySensorEntityDescription(
        key=XTDPCode.PIR_STATE,
        translation_key="pir_state",
        device_class=BinarySensorDeviceClass.MOTION,
        on_value="pir",
    ),
    XTBinarySensorEntityDescription(
        key=XTDPCode.PIR2,
        translation_key="pir_state",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
)

# All descriptions can be found here. Mostly the Boolean data types in the
# default status set of each category (that don't have a set instruction)
# end up being a binary sensor.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
BINARY_SENSORS: dict[str, tuple[XTBinarySensorEntityDescription, ...]] = {
    "jtmspro": (
        XTBinarySensorEntityDescription(
            key=XTDPCode.LOCK_MOTOR_STATE,
            translation_key="lock_motor_state",
            device_class=BinarySensorDeviceClass.LOCK,
            on_value=True,
        ),
    ),
    "kg": (*PROXIMITY_BINARY_SENSOR,),
    "msp": (
        # If 1 is reported, it will be counted once.
        # If 0 is reported, it will not be counted
        # (today and the average number of toilet visits will be counted on the APP)
        XTBinarySensorEntityDescription(
            key=XTDPCode.CLEANING_NUM,
            translation_key="cleaning_num",
        ),
        XTBinarySensorEntityDescription(
            key=XTDPCode.TRASH_STATUS,
            translation_key="trash_status",
            entity_registry_enabled_default=True,
            on_value="1",
        ),
        XTBinarySensorEntityDescription(
            key=XTDPCode.POWER,
            translation_key="power",
            entity_registry_enabled_default=False,
        ),
    ),
    "pir": (*PROXIMITY_BINARY_SENSOR,),
    # "qccdz": (
    #    XTBinarySensorEntityDescription(
    #        key=DPCode.ONLINE_STATE,
    #        translation_key="online",
    #        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    #        entity_registry_visible_default=False,
    #        device_online=True,
    #        on_value="online",
    #    ),
    # ),
    "smd": (
        XTBinarySensorEntityDescription(
            key=XTDPCode.OFF_BED,
            translation_key="off_bed",
        ),
        XTBinarySensorEntityDescription(
            key=XTDPCode.WAKEUP,
            translation_key="wakeup",
        ),
        XTBinarySensorEntityDescription(
            key=XTDPCode.OFF,
            translation_key="off",
        ),
    ),
}

BINARY_SENSORS["tdq"] = BINARY_SENSORS["kg"]

# Lock duplicates
BINARY_SENSORS["videolock"] = BINARY_SENSORS["jtmspro"]
BINARY_SENSORS["jtmsbh"] = BINARY_SENSORS["jtmspro"]


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya binary sensor dynamically through Tuya discovery."""
    hass_data = entry.runtime_data
    if hass_data.manager is None:
        return
    if entry.runtime_data.multi_manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, tuple[XTBinarySensorEntityDescription, ...]],
            dict[str, tuple[XTBinarySensorEntityDescription, ...]],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            BINARY_SENSORS, entry.runtime_data.multi_manager, Platform.BINARY_SENSOR
        ),
    )

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered Tuya binary sensor."""
        entities: list[XTBinarySensorEntity] = []
        device_ids = [*device_map]
        if hass_data.manager is None:
            return
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id, None):
                if category_descriptions := XTEntityDescriptorManager.get_category_descriptors(supported_descriptors, device.category):
                    externally_managed_dpcodes = (
                        XTEntityDescriptorManager.get_category_keys(
                            externally_managed_descriptors.get(device.category)
                        )
                    )
                    if restrict_dpcode is not None:
                        category_descriptions = cast(
                            tuple[XTBinarySensorEntityDescription, ...],
                            restrict_descriptor_category(
                                category_descriptions, [restrict_dpcode]
                            ),
                        )
                    entities.extend(
                        XTBinarySensorEntity.get_entity_instance(
                            description, device, hass_data.manager
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device, description, True, externally_managed_dpcodes
                        )
                    )
                    entities.extend(
                        XTBinarySensorEntity.get_entity_instance(
                            description, device, hass_data.manager
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device, description, False, externally_managed_dpcodes
                        )
                    )
        async_add_entities(entities)

    hass_data.manager.register_device_descriptors(
        Platform.BINARY_SENSOR, supported_descriptors
    )
    async_discover_device([*hass_data.manager.device_map])
    # async_discover_device(hass_data.manager, hass_data.manager.open_api_device_map)

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTBinarySensorEntity(XTEntity, TuyaBinarySensorEntity):
    """XT Binary Sensor Entity."""

    _entity_description: XTBinarySensorEntityDescription

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTBinarySensorEntityDescription,
    ) -> None:
        """Init Tuya binary sensor."""
        super(XTBinarySensorEntity, self).__init__(device, device_manager, description)
        super(XTEntity, self).__init__(device, device_manager, description)  # type: ignore
        self.device = device
        self.device_manager = device_manager
        self._entity_description = description

    @property
    def is_on(self) -> bool:
        is_on = super().is_on
        if self._entity_description.device_online:
            dpcode = self.entity_description.dpcode or self.entity_description.key
            self.device.online_states[dpcode] = is_on
            self.device_manager.update_device_online_status(self.device.id)
        return is_on

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()
        self.is_on  # Update the online status if needed

    @staticmethod
    def get_entity_instance(
        description: XTBinarySensorEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
    ) -> XTBinarySensorEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(device, device_manager, description)
        return XTBinarySensorEntity(
            device,
            device_manager,
            XTBinarySensorEntityDescription(**description.__dict__),
        )
