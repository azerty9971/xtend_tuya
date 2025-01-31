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

from .const import TUYA_DISCOVERY_NEW, LOGGER
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
    async def async_discover_device(device_map) -> None:
        """Discover and add a discovered Tuya camera."""
        entities: list[XTCameraEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if device.category in merged_categories:
                    if await XTCameraEntity.should_entity_be_added(hass, device, hass_data.manager):
                        entities.append(XTCameraEntity(device, hass_data.manager))

        async_add_entities(entities)

    await async_discover_device([*hass_data.manager.device_map])

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
    async def should_entity_be_added(hass: HomeAssistant, device: XTDevice, multi_manager: MultiManager) -> bool:
        if await hass.async_add_executor_job(multi_manager.get_device_stream_allocate, device.id, "rtsp"):
            LOGGER.warning(f"Device {device.name} added as camera")
            return True
        LOGGER.warning(f"Device {device.name} NOT added as camera")
        return False
