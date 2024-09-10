from dataclasses import dataclass, field

from .xt_tuya_iot_mq import (
    XTIOTOpenMQ,
)
from .xt_tuya_iot_home_manager import (
    XTIOTHomeManager,
)
from .xt_tuya_iot_manager import (
    XTIOTDeviceManager
)

@dataclass
class TuyaIOTData:
    device_manager: XTIOTDeviceManager = None
    mq: XTIOTOpenMQ = None
    device_ids: list[str] = field(default_factory=list) #List of device IDs that are managed by the manager before the managers device merging process
    home_manager: XTIOTHomeManager = None