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
    XTDPCode,
    DPType,
    LOGGER,
    CROSS_CATEGORY_DEVICE_DESCRIPTOR,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaLightEntity,
    TuyaLightEntityDescription,
    TuyaDPCode,
)
from .entity import (
    XTEntity,
)

@dataclass(frozen=True)
class XTLightEntityDescription(TuyaLightEntityDescription):
    """Describe an Tuya light entity."""
    brightness_max: TuyaDPCode | XTDPCode | None = None # type: ignore
    brightness_min: TuyaDPCode | XTDPCode | None = None # type: ignore
    brightness: TuyaDPCode | tuple[TuyaDPCode, ...] | XTDPCode | tuple[XTDPCode, ...] | None = None # type: ignore
    color_data: TuyaDPCode | tuple[TuyaDPCode, ...] | XTDPCode | tuple[XTDPCode, ...] | None = None # type: ignore
    color_mode: TuyaDPCode | XTDPCode | None = None # type: ignore
    color_temp: TuyaDPCode | tuple[TuyaDPCode, ...] | XTDPCode | tuple[XTDPCode, ...] | None = None # type: ignore

    def get_entity_instance(self, 
                            device: XTDevice, 
                            device_manager: MultiManager, 
                            description: XTLightEntityDescription
                            ) -> XTLightEntity:
        return XTLightEntity(device=device, 
                              device_manager=device_manager, 
                              description=description)

LIGHTS: dict[str, tuple[XTLightEntityDescription, ...]] = {
    "dbl": (
        XTLightEntityDescription(
            key=XTDPCode.LIGHT,
            translation_key="light",
            brightness=XTDPCode.BRIGHT_VALUE,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up tuya light dynamically through tuya discovery."""
    hass_data = entry.runtime_data

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    merged_descriptors = LIGHTS
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.LIGHT):
        merged_descriptors = merge_device_descriptors(merged_descriptors, new_descriptor)

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered tuya light."""
        if hass_data.manager is None:
            return
        entities: list[XTLightEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if descriptions := merged_descriptors.get(device.category):
                    entities.extend(
                        XTLightEntity.get_entity_instance(description, device, hass_data.manager)
                        for description in descriptions
                        if description.key in device.status and (restrict_dpcode is None or restrict_dpcode == description.key)
                    )
                if descriptions := merged_descriptors.get(CROSS_CATEGORY_DEVICE_DESCRIPTOR):
                    entities.extend(
                        XTLightEntity.get_entity_instance(description, device, hass_data.manager)
                        for description in descriptions
                        if description.key in device.status and (restrict_dpcode is None or restrict_dpcode == description.key)
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
        super(XTEntity, self).__init__(device, device_manager, description) # type: ignore
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description
    
    @staticmethod
    def get_entity_instance(description: XTLightEntityDescription, device: XTDevice, device_manager: MultiManager) -> XTLightEntity:
        if hasattr(description, "get_entity_instance") and callable(getattr(description, "get_entity_instance")):
            return description.get_entity_instance(device, device_manager, description)
        return XTLightEntity(device, device_manager, XTLightEntityDescription(**description.__dict__))