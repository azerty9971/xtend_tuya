"""Support for XT Fan."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .util import (
    append_sets
)

from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .const import TUYA_DISCOVERY_NEW
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaFanEntity,
)
from .entity import (
    XTEntity,
)

XT_SUPPORT_TYPE = {
}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up tuya fan dynamically through tuya discovery."""
    hass_data = entry.runtime_data

    merged_categories = XT_SUPPORT_TYPE
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.FAN):
        merged_categories = append_sets(merged_categories, new_descriptor)

    @callback
    def async_discover_device(device_map) -> None:
        """Discover and add a discovered tuya fan."""
        entities: list[XTFanEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if device and device.category in merged_categories:
                    entities.append(XTFanEntity(device, hass_data.manager))
        async_add_entities(entities)

    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTFanEntity(XTEntity, TuyaFanEntity):
    """XT Fan Device."""

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
    ) -> None:
        """Init XT Fan Device."""
        super(XTFanEntity, self).__init__(device, device_manager)
        self.device = device
        self.device_manager = device_manager