"""Support for Tuya Vacuums."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .multi_manager.multi_manager import (
    MultiManager,
    XTConfigEntry,
    XTDevice,
)
from .const import TUYA_DISCOVERY_NEW
from .util import (
    append_lists
)
from .entity import (
    XTEntity,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaVacuumEntity,
)

async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya vacuum dynamically through Tuya discovery."""
    hass_data = entry.runtime_data
    
    category_list: list[str] = []
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.VACUUM):
        category_list = append_lists(category_list, new_descriptor)
    
    @callback
    def async_discover_device(device_map) -> None:
        """Discover and add a discovered Tuya vacuum."""
        entities: list[XTVacuumEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if device.category in category_list:
                    entities.append(XTVacuumEntity(device, hass_data.manager))
        async_add_entities(entities)

    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTVacuumEntity(XTEntity, TuyaVacuumEntity):
    """XT Vacuum Device."""

    def __init__(self, device: XTDevice, device_manager: MultiManager) -> None:
        """Init Tuya vacuum."""
        super(XTVacuumEntity, self).__init__(device, device_manager)
        self.device = device
        self.device_manager = device_manager