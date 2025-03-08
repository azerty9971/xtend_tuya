"""Support for XT buttons."""

from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.const import EntityCategory, Platform
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

from .const import TUYA_DISCOVERY_NEW, DPCode, VirtualFunctions
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaButtonEntity,
    TuyaButtonEntityDescription,
)
from .entity import (
    XTEntity,
)

@dataclass(frozen=True)
class XTButtonEntityDescription(TuyaButtonEntityDescription):
    virtual_function: VirtualFunctions | None = None
    vf_reset_state: list[DPCode]  | None = field(default_factory=list)

CONSUMPTION_BUTTONS: tuple[XTButtonEntityDescription, ...] = (
    XTButtonEntityDescription(
            key=DPCode.RESET_ADD_ELE,
            virtual_function = VirtualFunctions.FUNCTION_RESET_STATE,
            vf_reset_state=[DPCode.ADD_ELE],
            translation_key="reset_add_ele",
            entity_category=EntityCategory.CONFIG,
    ),
)

# All descriptions can be found here.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
BUTTONS: dict[str, tuple[XTButtonEntityDescription, ...]] = {
    "jtmspro": (
        XTButtonEntityDescription(
            key=DPCode.MANUAL_LOCK,
            translation_key="manual_lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "kg": (
        *CONSUMPTION_BUTTONS,
    ),
    "qccdz": (
        XTButtonEntityDescription(
            key=DPCode.CLEAR_ENERGY,
            translation_key="clear_energy",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "xfj": (
        XTButtonEntityDescription(
            key=DPCode.FILTER_RESET,
            translation_key="filter_reset",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
}

BUTTONS["cz"]   = BUTTONS["kg"]
BUTTONS["wkcz"] = BUTTONS["kg"]
BUTTONS["dlq"]  = BUTTONS["kg"]
BUTTONS["tdq"]  = BUTTONS["kg"]
BUTTONS["pc"]   = BUTTONS["kg"]
BUTTONS["aqcz"] = BUTTONS["kg"]

#Lock duplicates
BUTTONS["videolock"] = BUTTONS["jtmspro"]

async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya buttons dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    merged_descriptors = BUTTONS
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.BUTTON):
        merged_descriptors = merge_device_descriptors(merged_descriptors, new_descriptor)

    @callback
    def async_discover_device(device_map) -> None:
        """Discover and add a discovered Tuya buttons."""
        entities: list[XTButtonEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if descriptions := merged_descriptors.get(device.category):
                    entities.extend(
                        XTButtonEntity(device, hass_data.manager, description)
                        for description in descriptions
                        if description.key in device.status
                    )
                    for description in descriptions:
                        if description.vf_reset_state:
                            for reset_state in description.vf_reset_state:
                                if reset_state in device.status:
                                    entities.extend(
                                        [XTButtonEntity(device, hass_data.manager, XTButtonEntityDescription(**description.__dict__))]
                                    )
                                break

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors("buttons", merged_descriptors)
    async_discover_device([*hass_data.manager.device_map])
    #async_discover_device(hass_data.manager, hass_data.manager.open_api_device_map)

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTButtonEntity(XTEntity, TuyaButtonEntity):
    """XT Button Device."""

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTButtonEntityDescription,
    ) -> None:
        """Init XT button."""
        super(XTButtonEntity, self).__init__(device, device_manager, description)
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description
