from __future__ import annotations
from typing import NamedTuple
from homeassistant.config_entries import ConfigEntry
from .device import (
    XTDevice,
)
from ..multi_manager import (
    MultiManager,
)
from .multi_device_listener import (
    MultiDeviceListener,
)
from ...const import (
    LOGGER,
)
from .services.services import (
    ServiceManager,
)

class DeviceWatcher:
    def __init__(self, multi_manager: MultiManager) -> None:
        self.watched_dev_id = []
        self.multi_manager = multi_manager

    def is_watched(self, dev_id: str) -> bool:
        return dev_id in self.watched_dev_id
    
    def report_message(self, dev_id: str, message: str, device: XTDevice | None = None):
        if self.is_watched(dev_id):
            if dev_id in self.multi_manager.device_map:
                managed_device = self.multi_manager.device_map[dev_id]
                LOGGER.warning(f"DeviceWatcher for {managed_device.name} ({dev_id}): {message}")
            elif device:
                LOGGER.warning(f"DeviceWatcher for {device.name} ({dev_id}): {message}")
            else:
                LOGGER.warning(f"DeviceWatcher for {dev_id}: {message}")

class HomeAssistantXTData(NamedTuple):
    """Tuya data stored in the Home Assistant data object."""

    multi_manager: MultiManager = None
    listener: MultiDeviceListener = None
    service_manager: ServiceManager = None

    @property
    def manager(self) -> MultiManager:
        return self.multi_manager

type XTConfigEntry = ConfigEntry[HomeAssistantXTData]