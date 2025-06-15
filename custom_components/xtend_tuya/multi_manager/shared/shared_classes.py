from __future__ import annotations
from typing import NamedTuple, Any, Optional
from collections import UserDict
from dataclasses import dataclass
import copy
from enum import StrEnum
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from tuya_sharing import (
    CustomerDevice as TuyaDevice,
)

class DeviceWatcher:
    def __init__(self, multi_manager: MultiManager) -> None:
        self.watched_dev_id: list[str] = []
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

    multi_manager: MultiManager | None = None
    listener: MultiDeviceListener | None = None
    service_manager: ServiceManager | None = None

    @property
    def manager(self) -> MultiManager | None:
        return self.multi_manager

type XTConfigEntry = ConfigEntry[HomeAssistantXTData]

@dataclass
class XTDeviceStatusRange:
    code: str = ""
    type: str | None = None
    values: str = "{}"
    dp_id: int = 0

    def __repr__(self) -> str:
        return f"StatusRange(code={self.code}, type={self.type}, values={self.values}, dp_id={self.dp_id})"

    @staticmethod
    def from_compatible_status_range(status_range: Any):
        if hasattr(status_range, "code"):
            code = status_range.code
        else:
            code = ""
        if hasattr(status_range, "type"):
            type = status_range.type
        else:
            type = ""
        if hasattr(status_range, "values"):
            values = status_range.values
        else:
            values = "{}"
        if hasattr(status_range, "dp_id"):
            dp_id = status_range.dp_id
        else:
            dp_id = 0
        return XTDeviceStatusRange(code=code, type=type, values=values, dp_id=dp_id)

@dataclass
class XTDeviceFunction:
    code: str = ""
    type: str | None = None
    desc: str = ""
    name: str = ""
    values: str = "{}"
    dp_id: int = 0
    
    def __repr__(self) -> str:
        return f"Function(code={self.code}, type={self.type}, desc={self.desc}, name={self.name}, values={self.values}, dp_id={self.dp_id})"

    @staticmethod
    def from_compatible_function(function: Any):
        if hasattr(function, "code"):
            code = function.code
        else:
            code = ""
        if hasattr(function, "type"):
            type = function.type
        else:
            type = ""
        if hasattr(function, "values"):
            values = function.values
        else:
            values = "{}"
        if hasattr(function, "desc"):
            desc = function.desc
        else:
            desc = ""
        if hasattr(function, "name"):
            name = function.name
        else:
            name = ""
        if hasattr(function, "dp_id"):
            dp_id = function.dp_id
        else:
            dp_id = 0
        return XTDeviceFunction(code=code, type=type, desc=desc, name=name, values=values, dp_id=dp_id)

class XTDevice(TuyaDevice):
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
    local_strategy: dict[int, dict[str, Any]] = {}
    source: str
    online_states: dict[str, bool]
    data_model: dict[str, Any]
    function: dict[str, XTDeviceFunction]
    status_range: dict[str, XTDeviceStatusRange]
    force_open_api: Optional[bool] = False
    device_source_priority: int | None = None
    force_compatibility: bool = False   #Force the device functions/status_range/state to remain untouched after merging
    device_preference: dict[str, Any] = {}

    class XTDevicePreference(StrEnum):
        IS_A_COVER_DEVICE                   = "IS_A_COVER_DEVICE"
        LOCK_MANUAL_UNLOCK_COMMAND          = "LOCK_MANUAL_UNLOCK_COMMAND"
        LOCK_GET_SUPPORTED_UNLOCK_TYPES     = "_LOCK_GET_SUPPORTED_UNLOCK_TYPES"
        LOCK_GET_DOOR_LOCK_PASSWORD_TICKET  = "_LOCK_GET_DOOR_LOCK_PASSWORD_TICKET"
        LOCK_CALL_DOOR_OPERATE              = "_LOCK_CALL_DOOR_OPERATE"
        LOCK_CALL_DOOR_OPEN                 = "_LOCK_CALL_DOOR_OPEN"

    def __init__(self, **kwargs: Any) -> None:
        self.source = ""
        self.online_states = {}
        self.data_model = {}
        self.force_open_api = False

        self.id: str = ""
        self.name: str = ""
        self.local_key: str = ""
        self.category: str = ""
        self.product_id: str = ""
        self.product_name: str = ""
        self.sub: bool = False
        self.uuid: str = ""
        self.asset_id: str = ""
        self.online: bool = False
        self.icon: str = ""
        self.ip: str = ""
        self.time_zone: str = ""
        self.active_time = 0
        self.create_time = 0
        self.update_time = 0
        self.set_up: bool | None = False
        self.support_local: bool | None = False

        self.local_strategy = {}
        self.status = {}
        self.function = {} # type: ignore
        self.status_range = {} # type: ignore
        self.device_preference = {}
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

    @staticmethod
    def from_compatible_device(device: Any, source: str = "Compatible device", device_source_priority: int | None = None):
        #If the device is already an XT device return it right away
        if isinstance(device, XTDevice):
            return device
        
        new_device = XTDevice(**device.__dict__)
        new_device.source = source
        new_device.device_source_priority = device_source_priority

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
    
    def get_multi_manager(self, hass: HomeAssistant) -> MultiManager | None:
        return get_device_multi_manager(hass=hass, device=self)
    
    def get_preference(self, pref_id: str, ret_val_if_missing: Any | None = None) -> Any | None:
        return self.device_preference.get(pref_id, ret_val_if_missing)
    
    def set_preference(self, pref_id: str, pref_val: Any):
        self.device_preference[pref_id] = pref_val

class XTDeviceMap(UserDict[str, XTDevice]):

    device_source_priority: XTDeviceSourcePriority | None = None
    _original_ref: Any | None = None

    def __init__(self, iterable, device_source_priority: XTDeviceSourcePriority | None = None):
        super().__init__(**iterable)
        self._original_ref = iterable
        self.device_source_priority = device_source_priority
    
    def __setitem__(self, key, item):
        super().__setitem__(key, item)
        if self._original_ref is not None:
            self._original_ref[key] = item





from ..multi_manager import (
    MultiManager,
)
from .multi_device_listener import (
    MultiDeviceListener,
)
from ...const import (
    LOGGER,
    XTDeviceSourcePriority,
)
from .services.services import (
    ServiceManager,
)
from ...util import (
    get_device_multi_manager,
)