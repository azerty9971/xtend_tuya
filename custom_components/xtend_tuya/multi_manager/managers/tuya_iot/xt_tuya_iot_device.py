from __future__ import annotations

from typing import Any

from ....lib.tuya_iot.device import (
    SmartHomeDeviceManage,
    IndustrySolutionDeviceManage,
)
from .xt_tuya_iot_openapi import (
    XTIOTOpenAPI,
)


class XTSmartHomeDeviceManage(SmartHomeDeviceManage):
    api: XTIOTOpenAPI # type: ignore
    
    def __init__(self, api: XTIOTOpenAPI):
        super().__init__(api=api)

    # https://developer.tuya.com/en/docs/cloud/device-control?id=K95zu01ksols7#title-27-Get%20the%20specifications%20and%20properties%20of%20the%20device%2C%20including%20the%20instruction%20set%20and%20status%20set
    def get_device_specification(self, device_id: str) -> dict[str, Any]:
        return self.api.get(f"/v1.0/devices/{device_id}/specifications", allow_caching=True)


class XTIndustrySolutionDeviceManage(IndustrySolutionDeviceManage):
    api: XTIOTOpenAPI # type: ignore
        
    def __init__(self, api: XTIOTOpenAPI):
        super().__init__(api=api)

    # https://developer.tuya.com/en/docs/cloud/device-control?id=K95zu01ksols7#title-27-Get%20the%20specifications%20and%20properties%20of%20the%20device%2C%20including%20the%20instruction%20set%20and%20status%20set
    def get_device_specification(self, device_id: str) -> dict[str, str]:
        return self.api.get(f"/v1.0/iot-03/devices/{device_id}/specification", allow_caching=True)
