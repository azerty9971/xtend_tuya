from __future__ import annotations

from dataclasses import dataclass
from datetime import time, datetime

from homeassistant.core import HomeAssistant, callback
from homeassistant.components.time import (
    TimeEntity,
    TimeEntityDescription,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import Platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    TUYA_DISCOVERY_NEW,
)
from .util import (
    merge_device_descriptors,
)
from .multi_manager.multi_manager import (
    MultiManager,
    XTConfigEntry,
    XTDevice,
)
from .entity import (
    XTEntity,
)

@dataclass(frozen=True)
class XTTimeEntityDescription(TimeEntityDescription):
    """Describes a Tuya time."""
    pass

TIMES: dict[str, tuple[XTTimeEntityDescription, ...]] = {
    
}

async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya binary sensor dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    merged_descriptors = TIMES
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.TIME):
        merged_descriptors = merge_device_descriptors(merged_descriptors, new_descriptor)

    @callback
    def async_discover_device(device_map) -> None:
        """Discover and add a discovered Tuya binary sensor."""
        entities: list[XTTimeEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if descriptions := merged_descriptors.get(device.category):
                    entities.extend(
                        XTTimeEntity(device, hass_data.manager, description)
                        for description in descriptions
                        if description.key in device.status
                    )
        
        async_add_entities(entities)
    
    hass_data.manager.register_device_descriptors("times", merged_descriptors)
    async_discover_device([*hass_data.manager.device_map])
    #async_discover_device(hass_data.manager, hass_data.manager.open_api_device_map)

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )

class XTTimeEntity(XTEntity, TimeEntity):
    """XT Time entity."""

    entity_description: XTTimeEntityDescription

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTTimeEntityDescription,
    ) -> None:
        """Init XT time."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self.device = device
        self.device_manager = device_manager

    @property
    def native_value(self) -> time | None:
        """Return the latest value."""
        return datetime.now().time()

    def set_value(self, value: time) -> None:
        """Change the time."""
        raise NotImplementedError
    