"""Support for the XT lights."""
from __future__ import annotations

import json

from dataclasses import dataclass

from homeassistant.const import Platform
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
from .const import (
    TUYA_DISCOVERY_NEW, 
    DPCode,
    DPType,
    LOGGER,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaLightEntity,
    TuyaLightEntityDescription,
)
from .entity import (
    XTEntity,
)

@dataclass(frozen=True)
class XTLightEntityDescription(TuyaLightEntityDescription):
    """Describe an Tuya light entity."""
    pass

LIGHTS: dict[str, tuple[XTLightEntityDescription, ...]] = {
    "dbl": (
        XTLightEntityDescription(
            key=DPCode.LIGHT,
            translation_key="light",
            brightness=DPCode.BRIGHT_VALUE,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up tuya light dynamically through tuya discovery."""
    hass_data = entry.runtime_data

    merged_descriptors = LIGHTS
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.LIGHT):
        merged_descriptors = merge_device_descriptors(merged_descriptors, new_descriptor)

    @callback
    def async_discover_device(device_map):
        """Discover and add a discovered tuya light."""
        entities: list[XTLightEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if descriptions := merged_descriptors.get(device.category):
                    entities.extend(
                        XTLightEntity(device, hass_data.manager, XTLightEntityDescription(**description.__dict__))
                        for description in descriptions
                        if description.key in device.status
                    )

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors("lights", merged_descriptors)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTLightEntity(XTEntity, TuyaLightEntity):
    """XT light device."""

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTLightEntityDescription,
    ) -> None:
        try:
            super(XTLightEntity, self).__init__(device, device_manager, description)
        except Exception as e:
            if (
                dpcode := self.find_dpcode(description.color_data, prefer_function=True)
            ) and self.get_dptype(dpcode) == DPType.JSON:
                if dpcode in self.device.function:
                    values = self.device.function[dpcode].values
                else:
                    values = self.device.status_range[dpcode].values
                if function_data := json.loads(values):
                    #LOGGER.warning(f"Failed light: {device}")
                    pass
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description