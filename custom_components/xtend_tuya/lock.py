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
    XTDPCode,
)
from .util import (
    append_dictionnaries,
)
from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaEntity,
)
from .entity import (
    XTEntity,
)

@dataclass(frozen=True)
class XTLockEntityDescription(LockEntityDescription):
    """Describes a Tuya lock."""
    unlock_status_list: list[XTDPCode] = field(default_factory=list)
    temporary_unlock: bool = False

LOCKS: dict[str, XTLockEntityDescription] = {
    "jtmspro": XTLockEntityDescription(
            key=None,
            translation_key="operate_lock",
            unlock_status_list=[XTDPCode.LOCK_MOTOR_STATE],
        ),
    "mk": XTLockEntityDescription(
            key=None,
            translation_key="operate_lock",
            temporary_unlock = True,
        ),
    "ms": XTLockEntityDescription(
            key=None,
            translation_key="operate_lock",
            unlock_status_list=[XTDPCode.LOCK_MOTOR_STATE],
        ),
    "videolock": XTLockEntityDescription(
            key=None,
            translation_key="operate_lock",
            unlock_status_list=[XTDPCode.LOCK_MOTOR_STATE],
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
        entities: list[XTLockEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if device.category in merged_descriptors:
                    entities.append(XTLockEntity(
                                    device, hass_data.manager, merged_descriptors[device.category]
                                ))
        async_add_entities(entities)

    async_discover_device([*hass_data.manager.device_map])
    #async_discover_device(hass_data.manager, hass_data.manager.open_api_device_map)

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )

class XTLockEntity(XTEntity, LockEntity):
    """Tuya Lock Sensor Entity."""

    entity_description: XTLockEntityDescription

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTLockEntityDescription,
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
        if self.entity_description.temporary_unlock:
            return True
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
        if self.entity_description.temporary_unlock:
            return False
        """Return true if the lock is locking."""
        is_locked = self.is_locked
        if self._attr_is_locking and is_locked:
            self._attr_is_locking = False
        return self._attr_is_locking

    @property
    def is_unlocking(self) -> bool | None:
        if self.entity_description.temporary_unlock:
            return False
        """Return true if the lock is unlocking."""
        is_locked = self.is_locked
        if self._attr_is_unlocking and not is_locked:
            self._attr_is_unlocking = False
        return self._attr_is_unlocking

    def _get_state_value(self, codes: list[XTDPCode]) -> Any | None:
        for code in codes:
            if str(code) in self.device.status:
                return self.device.status[str(code)]
        return None

    def lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        if self.device_manager.send_lock_unlock_command(self.device.id, True):
            if not self.entity_description.temporary_unlock:
                self._attr_is_locking = True
    
    def unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        if self.device_manager.send_lock_unlock_command(self.device.id, False):
            if not self.entity_description.temporary_unlock:
                self._attr_is_unlocking = True
    
    def open(self, **kwargs: Any) -> None:
        """Open the door latch."""
        raise NotImplementedError