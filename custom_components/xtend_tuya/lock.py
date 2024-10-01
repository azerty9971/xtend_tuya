from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.components.lock import (
    LockEntity,
    LockEntityDescription,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import Platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    LOGGER,  # noqa: F401
    TUYA_DISCOVERY_NEW,
    DPCode,
)
from .util import (
    append_dictionnaries,
)
from .base import TuyaEntity
from .multi_manager.shared.device import (
    XTDevice,
)
from .multi_manager.multi_manager import (
    MultiManager,
    XTConfigEntry,
)

@dataclass(frozen=True)
class TuyaLockEntityDescription(LockEntityDescription):
    """Describes a Tuya lock."""
    unlock_status_list: list[DPCode] = field(default_factory=list)

LOCKS: dict[str, TuyaLockEntityDescription] = {
    "mk": TuyaLockEntityDescription(
            key=None,
            translation_key="generic_lock",
        ),
    "jtmspro": TuyaLockEntityDescription(
            key=None,
            translation_key="generic_lock",
            unlock_status_list=[DPCode.LOCK_MOTOR_STATE]
        ),
}

async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya binary sensor dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    merged_descriptors = LOCKS
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.LOCK):
        merged_descriptors = append_dictionnaries(merged_descriptors, new_descriptor)

    @callback
    def async_discover_device(device_map) -> None:
        """Discover and add a discovered Tuya binary sensor."""
        entities: list[TuyaLockEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if device.category in merged_descriptors:
                    entities.append(TuyaLockEntity(
                                    device, hass_data.manager, merged_descriptors[device.category]
                                ))
        async_add_entities(entities)

    async_discover_device([*hass_data.manager.device_map])
    #async_discover_device(hass_data.manager, hass_data.manager.open_api_device_map)

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )

class TuyaLockEntity(TuyaEntity, LockEntity):
    """Tuya Lock Sensor Entity."""

    entity_description: TuyaLockEntityDescription

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: TuyaLockEntityDescription,
    ) -> None:
        """Init Tuya Lock sensor."""
        super().__init__(device, device_manager)
        self.device = device
        self.device_manager = device_manager
        self.last_action: str = None
        self.entity_description = description

    @property
    def is_locked(self) -> bool | None:
        """Return true if the lock is locked."""
        is_unlocked = self._get_state_value(self.entity_description.unlock_status_list)
        if is_unlocked is not None:
            if not is_unlocked:
                self._attr_is_locked = True
            else:
                self._attr_is_locked = False
        else:
            self._attr_is_locked = None
        return self._attr_is_locked
    
    @property
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""
        is_locked = self.is_locked
        if self._attr_is_locking and is_locked:
            self._attr_is_locking = False
        return self._attr_is_locking

    @property
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""
        is_locked = self.is_locked
        if self._attr_is_unlocking and not is_locked:
            self._attr_is_unlocking = False
        return self._attr_is_unlocking

    def _get_state_value(self, codes: list[DPCode]) -> Any | None:
        for code in codes:
            if str(code) in self.device.status:
                return self.device.status[str(code)]
        return None

    def lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        if self.device_manager.send_lock_unlock_command(self.device.id, True):
            self._attr_is_locking = True
            pass
    
    def unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        if self.device_manager.send_lock_unlock_command(self.device.id, False):
            self._attr_is_unlocking = True
            pass
    
    def open(self, **kwargs: Any) -> None:
        """Open the door latch."""
        raise NotImplementedError