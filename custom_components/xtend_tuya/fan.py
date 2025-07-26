"""Support for XT Fan."""

from __future__ import annotations
from typing import cast
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
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
    XTEntityDescriptorManager,
)

XT_SUPPORT_TYPE = {
    "xfj",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up tuya fan dynamically through tuya discovery."""
    hass_data = entry.runtime_data

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[set[str], set[str]],
        XTEntityDescriptorManager.get_platform_descriptors(
            XT_SUPPORT_TYPE, entry.runtime_data.multi_manager, Platform.FAN
        ),
    )

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered tuya fan."""
        if hass_data.manager is None:
            return
        if restrict_dpcode is not None:
            return None
        entities: list[XTFanEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if device and device.category in supported_descriptors:
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
        super(XTEntity, self).__init__(device, device_manager)  # type: ignore
        self.device = device
        self.device_manager = device_manager
