from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, cast
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
    XTMultiManagerProperties,
)
from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)


@dataclass(frozen=True)
class XTLockEntityDescription(LockEntityDescription):
    """Describes a Tuya lock."""

    unlock_status_list: list[XTDPCode] = field(default_factory=list)
    temporary_unlock: bool = False
    manual_unlock_command: list[XTDPCode] = field(default_factory=list)

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTLockEntityDescription,
    ) -> XTLockEntity:
        return XTLockEntity(
            device=device, device_manager=device_manager, description=description
        )


# LOCKS are now dynamically added
# if you want a specific translation key or something
# non-generic then add the category and descriptor in the list
LOCKS: dict[str, XTLockEntityDescription] = {}

# Statuses that tell if the lock is currently locked or not
LOCK_LOCKED_UNLOCKED_STATUS_DPCODES: list[XTDPCode] = [
    XTDPCode.LOCK_MOTOR_STATE,
    XTDPCode.ACCESSORY_LOCK,
]

# Statuses that can be sent to lock/unlock the lock
LOCK_MANUAL_COMMAND_DPCODES: list[XTDPCode] = [
    XTDPCode.ACCESSORY_LOCK,
    XTDPCode.BLUETOOTH_UNLOCK,
]

# Statuses that are used to determine if the device is a lock or not
LOCK_IS_LOCK_DPCODES: list[XTDPCode] = [
    XTDPCode.UNLOCK_METHOD_CREATE,
    XTDPCode.UNLOCK_METHOD_DELETE,
    XTDPCode.UNLOCK_METHOD_MODIFY,
    XTDPCode.MANUAL_LOCK,
    XTDPCode.LOCK_RECORD,
    XTDPCode.UNLOCK_BLE,
    XTDPCode.UNLOCK_CARD,
    XTDPCode.UNLOCK_FACE,
    XTDPCode.UNLOCK_FINGER_VEIN,
    XTDPCode.UNLOCK_FINGERPRINT,
    XTDPCode.UNLOCK_HAND,
    XTDPCode.UNLOCK_KEY,
    XTDPCode.UNLOCK_PASSWORD,
    XTDPCode.UNLOCK_PHONE_REMOTE,
    XTDPCode.UNLOCK_VOICE_REMOTE,
]


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya binary sensor dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[dict[str, XTLockEntityDescription], dict[str, XTLockEntityDescription]],
        XTEntityDescriptorManager.get_platform_descriptors(
            LOCKS, entry.runtime_data.multi_manager, Platform.LOCK
        ),
    )

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered Tuya binary sensor."""
        if hass_data.manager is None:
            return
        if restrict_dpcode is not None:
            return None
        entities: list[XTLockEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if description := XTLockEntity.get_entity_description(
                    hass, device, hass_data.manager, supported_descriptors
                ):
                    entities.append(
                        XTLockEntity.get_entity_instance(
                            description, device, hass_data.manager
                        )
                    )
        async_add_entities(entities)

    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTLockEntity(XTEntity, LockEntity):  # type: ignore
    """Tuya Lock Sensor Entity."""

    entity_description: XTLockEntityDescription
    temporary_unlock: bool = False

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
        self.last_action: str | None = None
        self.entity_description = description  # type: ignore
        self.temporary_unlock = description.temporary_unlock
        if self._get_state_value(self.entity_description.unlock_status_list) is None:
            # If we can't find the status of the lock then assume a temporary lock
            self.temporary_unlock = True
        device_manager.set_general_property(
            XTMultiManagerProperties.LOCK_DEVICE_ID, device.id
        )
        if len(description.manual_unlock_command) > 0:
            manual_unlock_commands: list[XTDPCode] = []
            for unlock_command in description.manual_unlock_command:
                if unlock_command in device.status:
                    manual_unlock_commands.append(unlock_command)
            if len(manual_unlock_commands) > 0:
                device.set_preference(
                    f"{XTDevice.XTDevicePreference.LOCK_MANUAL_UNLOCK_COMMAND}",
                    manual_unlock_commands,
                )

    @staticmethod
    def should_entity_be_added(
        hass: HomeAssistant,
        device: XTDevice,
        multi_manager: MultiManager,
        merged_descriptors: dict[str, XTLockEntityDescription],
    ) -> bool:
        if device.category in merged_descriptors:
            return True
        for test_status in LOCK_IS_LOCK_DPCODES:
            if test_status in device.status:
                return True
        for test_status in LOCK_LOCKED_UNLOCKED_STATUS_DPCODES:
            if test_status in device.status:
                return True
        for test_status in LOCK_MANUAL_COMMAND_DPCODES:
            if test_status in device.status:
                return True
        return False

    @staticmethod
    def get_entity_description(
        hass: HomeAssistant,
        device: XTDevice,
        multi_manager: MultiManager,
        merged_descriptors: dict[str, XTLockEntityDescription],
    ) -> XTLockEntityDescription | None:
        if XTLockEntity.should_entity_be_added(
            hass, device, multi_manager, merged_descriptors
        ):
            if entity_description := merged_descriptors.get(device.category):
                return entity_description
            unlock_status_list: list[XTDPCode] = []
            manual_unlock_command_list: list[XTDPCode] = []
            temporary_unlock: bool = True
            for dpcode in LOCK_LOCKED_UNLOCKED_STATUS_DPCODES:
                if dpcode in device.status:
                    unlock_status_list.append(dpcode)
            if unlock_status_list:
                temporary_unlock = False
            for dpcode in LOCK_MANUAL_COMMAND_DPCODES:
                if dpcode in device.status:
                    manual_unlock_command_list.append(dpcode)
            return XTLockEntityDescription(
                key="",
                translation_key="operate_lock",
                unlock_status_list=unlock_status_list,
                manual_unlock_command=manual_unlock_command_list,
                temporary_unlock=temporary_unlock,
            )
        return None

    @property
    def is_locked(self) -> bool | None:  # type: ignore
        """Return true if the lock is locked."""
        if self.temporary_unlock:
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
    def is_locking(self) -> bool | None:  # type: ignore
        if self.temporary_unlock:
            return False
        """Return true if the lock is locking."""
        is_locked = self.is_locked
        if self._attr_is_locking and is_locked:
            self._attr_is_locking = False
        return self._attr_is_locking

    @property
    def is_unlocking(self) -> bool | None:  # type: ignore
        if self.temporary_unlock:
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
        if self.device_manager.send_lock_unlock_command(self.device, True):
            if not self.temporary_unlock:
                self._attr_is_locking = True

    def unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        if self.device_manager.send_lock_unlock_command(self.device, False):
            if not self.temporary_unlock:
                self._attr_is_unlocking = True

    def open(self, **kwargs: Any) -> None:
        """Open the door latch."""
        raise NotImplementedError

    @staticmethod
    def get_entity_instance(
        description: XTLockEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
    ) -> XTLockEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(device, device_manager, description)
        return XTLockEntity(
            device, device_manager, XTLockEntityDescription(**description.__dict__)
        )
