from __future__ import annotations

from typing import Any, Optional
from types import SimpleNamespace
from dataclasses import dataclass, field
import copy
import json

@dataclass
class XTDeviceStatusRange:
    code: str
    type: str
    values: str

    def from_compatible_status_range(status_range: Any):
        if hasattr(status_range, "code"):
            code = status_range.code
        else:
            code = None
        if hasattr(status_range, "type"):
            type = status_range.type
        else:
            type = None
        if hasattr(status_range, "values"):
            values = status_range.values
        else:
            values = None
        return XTDeviceStatusRange(code=code, type=type, values=values)

@dataclass
class XTDeviceFunction:
    code: str
    type: str
    desc: str = None
    name: str = None
    values: dict[str, Any] = field(default_factory=dict)
    
    def from_compatible_function(function: Any):
        if hasattr(function, "code"):
            code = function.code
        else:
            code = None
        if hasattr(function, "type"):
            type = function.type
        else:
            type = None
        if hasattr(function, "values"):
            values = function.values
        else:
            values = None
        if hasattr(function, "desc"):
            desc = function.desc
        else:
            desc = None
        if hasattr(function, "name"):
            name = function.name
        else:
            name = None
        return XTDeviceFunction(code=code, type=type, desc=desc, name=name, values=values)

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
    
    def __repr__(self) -> str:
        return f"Device {self.name}:\r\nfunctions: {json.dumps(self.function, indent=2)}\r\n\r\nstatus_ranges: {json.dumps(self.status_range, indent=2)}\r\n\r\nstatuses: {json.dumps(self.status, indent=2)}\r\n\r\nlocal_strategies: {json.dumps(self.local_strategy, indent=2)}"

    def from_compatible_device(device: Any):
        new_device = XTDevice(**(device.__dict__))
        
        #Reuse the references from the original device
        if hasattr(device, "local_strategy"):
            new_device.local_strategy = device.local_strategy
        if hasattr(device, "status"):
            new_device.status = device.status
        if hasattr(device, "function"):
            new_device.function = device.function
        if hasattr(device, "status_range"):
            new_device.status_range = device.status_range

        return new_device
    
    """def copy_data_from_device(source_device, dest_device) -> None:
        if hasattr(source_device, "online") and hasattr(dest_device, "online"):
            dest_device.online = source_device.online
        if hasattr(source_device, "name") and hasattr(dest_device, "name"):
            dest_device.name = source_device.name
        if hasattr(source_device, "status") and hasattr(dest_device, "status"):
            for code, value in source_device.status.items():
                dest_device.status[code] = value"""

    def get_copy(self) -> XTDevice:
        return copy.deepcopy(self)