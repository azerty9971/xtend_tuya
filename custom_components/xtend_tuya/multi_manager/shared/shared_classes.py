from __future__ import annotations
from typing import Any, Optional
from types import SimpleNamespace
import copy
from dataclasses import dataclass, field
from ...util import (
    merge_iterables,
)

class DeviceWatcher:
    def __init__(self) -> None:
        self.watched_dev_id = ["bf48bc174fe06d1ea3z7ja"]
    
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

@dataclass
class XTDeviceStatusRange:
    code: str
    type: str
    values: str

@dataclass
class XTDeviceFunction:
    code: str
    desc: str
    name: str
    type: str
    values: dict[str, Any] = field(default_factory=dict)

class XTDevice(SimpleNamespace):
    id: str
    name: str
    local_key: str
    category: str
    product_id: str
    product_name: str
    sub: bool
    uuid: str
    asset_id: str
    online: bool
    icon: str
    ip: str
    time_zone: str
    active_time: int
    create_time: int
    update_time: int
    local_key: str
    set_up: Optional[bool] = False
    support_local: Optional[bool] = False
    local_strategy: dict[int, dict[str, Any]]

    status: dict[str, Any]
    function: dict[str, XTDeviceFunction]
    status_range: dict[str, XTDeviceStatusRange]

    force_open_api: Optional[bool] = False
    data_model: Optional[str] = ""

    def __init__(self, **kwargs: Any) -> None:
        self.local_strategy = {}
        self.status = {}
        self.function = {}
        self.status_range = {}
        super().__init__(**kwargs)

    def __eq__(self, other):
        """If devices are the same one."""
        return self.id == other.id

    def from_compatible_device(device):
        return XTDevice(**(device.__dict__))
    
    def copy_data_from_device(source_device, dest_device) -> None:
        if hasattr(source_device, "online") and hasattr(dest_device, "online"):
            dest_device.online = source_device.online
        if hasattr(source_device, "name") and hasattr(dest_device, "name"):
            dest_device.name = source_device.name
        if hasattr(source_device, "status") and hasattr(dest_device, "status"):
            for code, value in source_device.status.items():
                dest_device.status[code] = value