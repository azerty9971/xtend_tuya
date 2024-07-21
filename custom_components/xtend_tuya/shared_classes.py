from __future__ import annotations
from typing import Any

class XTDeviceProperties:  # noqa: F811
    local_strategy: dict[int, dict[str, Any]] = {}
    status: dict[str, Any] = {}
    function: dict[str, XTDeviceFunction] = {}
    status_range: dict[str, XTDeviceStatusRange] = {}

    def merge_in_device(self, device):
        if hasattr(device, "local_strategy"):
            device.local_strategy.update(self.local_strategy)
        if hasattr(device, "status"):
            device.status.update(self.status)
        if hasattr(device, "function"):
            device.function.update(self.function)
        if hasattr(device, "status_range"):
            device.status_range.update(self.status_range)

class XTDeviceStatusRange:  # noqa: F811
    code: str
    type: str
    values: str

class XTDeviceFunction:  # noqa: F811
    code: str
    desc: str
    name: str
    type: str
    values: dict[str, Any]