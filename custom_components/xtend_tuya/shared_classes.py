from __future__ import annotations
from typing import Any, Optional
from types import SimpleNamespace
from dataclasses import dataclass, field

@dataclass
class XTDeviceProperties:
    local_strategy: dict[int, dict[str, Any]] = field(default_factory=dict)
    status: dict[str, Any] = field(default_factory=dict)
    function: dict[str, XTDeviceFunction] = field(default_factory=dict)
    status_range: dict[str, XTDeviceStatusRange] = field(default_factory=dict)

    def merge_in_device(self, device):
        if hasattr(device, "local_strategy"):
            device.local_strategy.update(self.local_strategy)
        if hasattr(device, "status"):
            device.status.update(self.status)
        if hasattr(device, "function"):
            device.function.update(self.function)
        if hasattr(device, "status_range"):
            device.status_range.update(self.status_range)

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
    set_up: Optional[bool] = False
    support_local: Optional[bool] = False
    local_strategy: dict[int, dict[str, Any]]

    status: dict[str, Any]
    function: dict[str, XTDeviceFunction]
    status_range: dict[str, XTDeviceStatusRange]

    force_open_api: Optional[bool] = False
    model: Optional[dict] = ""

    def __init__(self, **kwargs: Any) -> None:
        self.local_strategy = {}
        self.status = {}
        self.function = {}
        self.status_range = {}
        super().__init__(**kwargs)

    def __eq__(self, other):
        """If devices are the same one."""
        return self.id == other.id

    def from_customer_device(device):
        return XTDevice(**(device.__dict__))