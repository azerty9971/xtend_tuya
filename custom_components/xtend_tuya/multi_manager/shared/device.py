from __future__ import annotations

from typing import Any, Optional
from types import SimpleNamespace
from dataclasses import dataclass, field
import copy
from tuya_sharing import (
    CustomerDevice as TuyaDevice,
)

@dataclass
class XTDeviceStatusRange:
    code: str
    type: str
    values: str
    dp_id: int = None

    def __repr__(self) -> str:
        return f"StatusRange(code={self.code}, type={self.type}, values={self.values}, dp_id={self.dp_id})"

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
        if hasattr(status_range, "dp_id"):
            dp_id = status_range.dp_id
        else:
            dp_id = None
        return XTDeviceStatusRange(code=code, type=type, values=values, dp_id=dp_id)

@dataclass
class XTDeviceFunction:
    code: str
    type: str
    desc: str = None
    name: str = None
    values: dict[str, Any] = field(default_factory=dict)
    dp_id: int = None
    
    def __repr__(self) -> str:
        return f"Function(code={self.code}, type={self.type}, desc={self.desc}, name={self.name}, values={self.values}, dp_id={self.dp_id})"

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
        if hasattr(function, "dp_id"):
            dp_id = function.dp_id
        else:
            dp_id = None
        return XTDeviceFunction(code=code, type=type, desc=desc, name=name, values=values, dp_id=dp_id)

class XTDevice(TuyaDevice):
    source: str
    online_states: dict[str, bool]
    data_model: dict[str, Any]
    force_open_api: Optional[bool] = False
    function: dict[str, XTDeviceFunction]
    status_range: dict[str, XTDeviceStatusRange]

    def __init__(self, **kwargs: Any) -> None:
        self.source = ""
        self.online_states = {}
        self.data_model = {}
        self.force_open_api = False

        self.id = ""
        self.name = ""
        self.local_key = ""
        self.category = ""
        self.product_id = ""
        self.product_name = ""
        self.sub = False
        self.uuid = ""
        self.asset_id = ""
        self.online = False
        self.icon = ""
        self.ip = ""
        self.time_zone = ""
        self.active_time = 0
        self.create_time = 0
        self.update_time = 0
        self.set_up = False
        self.support_local = False

        self.local_strategy = {}
        self.status = {}
        self.function = {}
        self.status_range = {}
        super().__init__(**kwargs)
    
    def __repr__(self) -> str:
        function_str = "Functions:\r\n"
        for function in self.function.values():
            function_str += f"{function}\r\n"
        status_range_str = "StatusRange:\r\n"
        for status_range in self.status_range.values():
            status_range_str += f"{status_range}\r\n"
        status_str = "Status:\r\n"
        for code in self.status:
            status_str += f"{code}: {self.status[code]}\r\n"
        local_strategy_str = "LocalStrategy:\r\n"
        for dpId in self.local_strategy:
            local_strategy_str += f"{dpId}\r\n{self.local_strategy[dpId]}\r\n"
        
        return f"Device {self.name}:\r\n{function_str}{status_range_str}{status_str}{local_strategy_str}"
        #return f"Device {self.name}:\r\n{self.source}"

    def from_compatible_device(device: Any, source: str = "Compatible device"):
        #If the device is already an XT device return it right away
        if isinstance(device, XTDevice):
            return device
        
        new_device = XTDevice(**device.__dict__)
        new_device.source = source

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