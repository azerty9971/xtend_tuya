from __future__ import annotations
from typing import Any

class XTDeviceProperties:  # noqa: F811
    local_strategy: dict[int, dict[str, Any]] = {}
    status: dict[str, Any] = {}
    function: dict[str, XTDeviceFunction] = {}
    status_range: dict[str, XTDeviceStatusRange] = {}

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