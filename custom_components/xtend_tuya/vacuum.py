"""Support for Tuya Vacuums."""

from __future__ import annotations
from typing import cast
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
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaVacuumEntity,
)

VACUUMS: list[str] = []

async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya vacuum dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            list[str],
            list[str],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            VACUUMS, entry.runtime_data.multi_manager, Platform.VACUUM
        ),
    )

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered Tuya vacuum."""
        if hass_data.manager is None:
            return
        if restrict_dpcode is not None:
            return None
        entities: list[XTVacuumEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if device.category in supported_descriptors:
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
        super(XTEntity, self).__init__(device, device_manager)  # type: ignore
        self.device = device
        self.device_manager = device_manager
