"""Support for XT Alarm."""

from __future__ import annotations

from homeassistant.const import (
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .util import (
    merge_device_descriptors
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaAlarmEntity,
    TuyaAlarmControlPanelEntityDescription,
)

from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .const import TUYA_DISCOVERY_NEW, CROSS_CATEGORY_DEVICE_DESCRIPTOR
from .entity import (
    XTEntity,
)

class XTAlarmEntityDescription(TuyaAlarmControlPanelEntityDescription):
    def __init__(self, *args, **kwargs):
        super(XTAlarmEntityDescription, self).__init__(*args, **kwargs)

    def get_entity_instance(self, 
                            device: XTDevice, 
                            device_manager: MultiManager, 
                            description: XTAlarmEntityDescription
                            ) -> XTAlarmEntity:
        return XTAlarmEntity(device=device, 
                              device_manager=device_manager, 
                              description=description)

# All descriptions can be found here:
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
ALARM: dict[str, tuple[XTAlarmEntityDescription, ...]] = {
}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya alarm dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    merged_descriptors = ALARM
    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.ALARM_CONTROL_PANEL):
        merged_descriptors = merge_device_descriptors(merged_descriptors, new_descriptor)

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered Tuya siren."""
        entities: list[XTAlarmEntity] = []
        device_ids = [*device_map]
        if hass_data.manager is None:
            return
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id, None):
                if descriptions := merged_descriptors.get(device.category):
                    entities.extend(
                        XTAlarmEntity.get_entity_instance(description, device, hass_data.manager)
                        for description in descriptions
                        if description.key in device.status and (restrict_dpcode is None or restrict_dpcode == description.key)
                    )
                if descriptions := merged_descriptors.get(CROSS_CATEGORY_DEVICE_DESCRIPTOR):
                    entities.extend(
                        XTAlarmEntity.get_entity_instance(description, device, hass_data.manager)
                        for description in descriptions
                        if description.key in device.status and (restrict_dpcode is None or restrict_dpcode == description.key)
                    )
        async_add_entities(entities)

    hass_data.manager.register_device_descriptors("alarm_control", merged_descriptors)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTAlarmEntity(XTEntity, TuyaAlarmEntity):
    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTAlarmEntityDescription,
    ) -> None:
        super(XTAlarmEntity, self).__init__(device, device_manager, description)
        super(XTEntity, self).__init__(device, device_manager, description) # type: ignore
    
    @staticmethod
    def get_entity_instance(description: XTAlarmEntityDescription, device: XTDevice, device_manager: MultiManager) -> XTAlarmEntity:
        if hasattr(description, "get_entity_instance") and callable(getattr(description, "get_entity_instance")):
            return description.get_entity_instance(device, device_manager, description)
        return XTAlarmEntity(device, device_manager, XTAlarmEntityDescription(**description.__dict__))