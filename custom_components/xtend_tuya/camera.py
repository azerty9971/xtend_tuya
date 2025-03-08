"""Support for XT cameras."""

from __future__ import annotations

import asyncio
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .util import (
    append_lists
)

from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)

from .const import TUYA_DISCOVERY_NEW, LOGGER, DPCode
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaCameraEntity,
)
from .entity import (
    XTEntity,
)

# All descriptions can be found here:
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
CAMERAS: tuple[str, ...] = (
    "jtmspro",
    "videolock",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya cameras dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    merged_categories = CAMERAS
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.CAMERA):
        merged_categories = tuple(append_lists(merged_categories, new_descriptor))

    @callback
    def async_discover_device(device_map) -> None:
        """Discover and add a discovered Tuya camera."""
        entities: list[XTCameraEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if device.category in merged_categories:
                    if XTCameraEntity.should_entity_be_added(hass, device, hass_data.manager):
                        entities.append(XTCameraEntity(device, hass_data.manager))

        async_add_entities(entities)

    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTCameraEntity(XTEntity, TuyaCameraEntity):
    """XT Camera Entity."""

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
    ) -> None:
        """Init XT Camera."""
        super(XTCameraEntity, self).__init__(device, device_manager)
        self.device = device
        self.device_manager = device_manager
    
    @staticmethod
    def should_entity_be_added(hass: HomeAssistant, device: XTDevice, multi_manager: MultiManager) -> bool:
        camera_status: list[DPCode] = [DPCode.RECORD_MODE, DPCode.IPC_WORK_MODE, DPCode.PHOTO_AGAIN]
        for test_status in camera_status:
            if test_status in device.status:
                return True
        if device.category in ["videolock"]:
            return True
        return False
