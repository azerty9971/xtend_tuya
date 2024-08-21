from typing import NamedTuple

from .xt_tuya_iot_mq import (
    XTIOTOpenMQ,
)
from .xt_tuya_iot_home_manager import (
    XTIOTHomeManager,
)
from .xt_tuya_iot_manager import (
    XTIOTDeviceManager
)

class TuyaIOTData(NamedTuple):
    device_manager: XTIOTDeviceManager
    mq: XTIOTOpenMQ
    device_ids: list[str] #List of device IDs that are managed by the manager before the managers device merging process
    home_manager: XTIOTHomeManager