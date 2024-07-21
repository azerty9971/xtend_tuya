from __future__ import annotations
from typing import Any

class XTDeviceProperties:
    local_strategy: dict[int, dict[str, Any]] = {}
    status: dict[str, Any] = {}
    function: dict[str, XTDeviceFunction] = {}
    status_range: dict[str, XTDeviceStatusRange] = {}

    def __init__(self) -> None:
        self.local_strategy = {}
        self.status = {}
        self.function = {}
        self.status_range = {}

    def merge_in_device(self, device):
        if hasattr(device, "local_strategy"):
            device.local_strategy.update(self.local_strategy)
        if hasattr(device, "status"):
            device.status.update(self.status)
        if hasattr(device, "function"):
            device.function.update(self.function)
        if hasattr(device, "status_range"):
            device.status_range.update(self.status_range)

class XTDeviceStatusRange:
    code: str
    type: str
    values: str

class XTDeviceFunction:
    code: str
    desc: str
    name: str
    type: str
    values: dict[str, Any]