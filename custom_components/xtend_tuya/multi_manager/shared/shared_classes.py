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

class DeviceWatcher:
    def __init__(self) -> None:
        self.watched_dev_id = ["bf0b40e8bb7732ac1drh8t", "bf38f31b4a36fc3ea5wlg9"]
    
    def is_watched(self, dev_id: str) -> bool:
        return dev_id in self.watched_dev_id

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