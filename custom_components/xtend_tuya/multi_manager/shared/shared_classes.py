from __future__ import annotations
from typing import Any, NamedTuple
import copy
from dataclasses import dataclass, field
from homeassistant.config_entries import ConfigEntry
from ...util import (
    merge_iterables,
)
from .device import (
    XTDeviceFunction,
    XTDeviceStatusRange,
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

class DeviceWatcher:
    def __init__(self, multi_manager: MultiManager) -> None:
        self.watched_dev_id = []
        self.multi_manager = multi_manager

    def is_watched(self, dev_id: str) -> bool:
        return dev_id in self.watched_dev_id
    
    def report_message(self, dev_id: str, message: str, device: any = None):
        if self.is_watched(dev_id):
            if dev_id in self.multi_manager.device_map:
                managed_device = self.multi_manager.device_map[dev_id]
                LOGGER.warning(f"DeviceWatcher for {managed_device.name} ({dev_id}): {message}")
            elif device:
                LOGGER.warning(f"DeviceWatcher for {device.name} ({dev_id}): {message}")

@dataclass
class XTDeviceProperties:
    local_strategy: dict[int, dict[str, Any]] = field(default_factory=dict)
    status: dict[str, Any] = field(default_factory=dict)
    function: dict[str, XTDeviceFunction] = field(default_factory=dict)
    status_range: dict[str, XTDeviceStatusRange] = field(default_factory=dict)
    data_model: str = field(default_factory=str)

    def merge_in_device(self, device):
        if hasattr(device, "local_strategy"):
            merge_iterables(device.local_strategy, self.local_strategy)
            #device.local_strategy.update(self.local_strategy)
        if hasattr(device, "status"):
            merge_iterables(device.status, self.status)
            #device.status.update(self.status)
        if hasattr(device, "function"):
            merge_iterables(device.function, self.function)
            #device.function.update(self.function)
        if hasattr(device, "status_range"):
            merge_iterables(device.status_range, self.status_range)
            #device.status_range.update(self.status_range)
        if hasattr(device, "data_model"):
            device.data_model = copy.deepcopy(self.data_model)

class HomeAssistantXTData(NamedTuple):
    """Tuya data stored in the Home Assistant data object."""

    multi_manager: MultiManager
    listener: MultiDeviceListener = None

    @property
    def manager(self) -> MultiManager:
        return self.multi_manager

type XTConfigEntry = ConfigEntry[HomeAssistantXTData]