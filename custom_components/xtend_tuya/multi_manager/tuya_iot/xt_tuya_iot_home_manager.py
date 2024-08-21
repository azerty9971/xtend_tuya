from __future__ import annotations

from tuya_iot import (
    TuyaDeviceManager,
    TuyaHomeManager,
    TuyaOpenAPI,
    TuyaOpenMQ,
)

from ..multi_manager import (
    MultiManager,
)

class XTIOTHomeManager(TuyaHomeManager):
    def __init__(
        self, api: TuyaOpenAPI, 
        mq: TuyaOpenMQ, 
        device_manager: TuyaDeviceManager,
        multi_manager: MultiManager
    ):
        super().__init__(api, mq, device_manager)
        self.multi_manager = multi_manager

    def update_device_cache(self):
        super().update_device_cache()
        #self.multi_manager.convert_tuya_devices_to_xt(self.device_manager)