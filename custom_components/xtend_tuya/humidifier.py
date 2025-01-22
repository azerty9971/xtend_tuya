"""Support for XT (de)humidifiers."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .util import (
    append_dictionnaries
)

from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .const import TUYA_DISCOVERY_NEW
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaHumidifierEntity,
    TuyaHumidifierEntityDescription,
)
from .entity import (
    XTEntity,
)

@dataclass(frozen=True)
class XTHumidifierEntityDescription(TuyaHumidifierEntityDescription):
    """Describe an XT (de)humidifier entity."""
    pass


HUMIDIFIERS: dict[str, XTHumidifierEntityDescription] = {
}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya (de)humidifier dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    merged_categories = HUMIDIFIERS
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.HUMIDIFIER):
        merged_categories = append_dictionnaries(merged_categories, new_descriptor)

    @callback
    def async_discover_device(device_map) -> None:
        """Discover and add a discovered Tuya (de)humidifier."""
        entities: list[XTHumidifierEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if description := merged_categories.get(device.category):
                    entities.append(
                        XTHumidifierEntity(device, hass_data.manager, XTHumidifierEntityDescription(**description.__dict__))
                    )
        async_add_entities(entities)

    hass_data.manager.register_device_descriptors("humidifiers", merged_categories)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTHumidifierEntity(XTEntity, TuyaHumidifierEntity):
    """XT (de)humidifier Device."""

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTHumidifierEntityDescription,
    ) -> None:
        super(XTHumidifierEntity, self).__init__(device, device_manager, description)
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description
