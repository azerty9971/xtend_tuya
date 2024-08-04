"""Support for Tuya buttons."""

from __future__ import annotations

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.components.tuya.button import (
    BUTTONS as BUTTONS_TUYA
)
from .util import (
    merge_device_descriptors
)

from .multi_manager import XTConfigEntry
from .base import TuyaEntity
from .const import TUYA_DISCOVERY_NEW, DPCode

# All descriptions can be found here.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
BUTTONS: dict[str, tuple[ButtonEntityDescription, ...]] = {
}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya buttons dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    merged_descriptors = BUTTONS
    if not entry.runtime_data.multi_manager.reuse_config:
        merged_descriptors = merge_device_descriptors(BUTTONS, BUTTONS_TUYA)

    @callback
    def async_discover_device(device_map) -> None:
        """Discover and add a discovered Tuya buttons."""
        entities: list[TuyaButtonEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            device = hass_data.manager.device_map[device_id]
            if descriptions := merged_descriptors.get(device.category):
                entities.extend(
                    TuyaButtonEntity(device, hass_data.manager, description)
                    for description in descriptions
                    if description.key in device.status
                )

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors("buttons", merged_descriptors)
    async_discover_device([*hass_data.manager.device_map])
    #async_discover_device(hass_data.manager, hass_data.manager.open_api_device_map)

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaButtonEntity(TuyaEntity, ButtonEntity):
    """Tuya Button Device."""

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: ButtonEntityDescription,
    ) -> None:
        """Init Tuya button."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

    def press(self) -> None:
        """Press the button."""
        self._send_command([{"code": self.entity_description.key, "value": True}])
