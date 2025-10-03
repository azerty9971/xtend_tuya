from __future__ import annotations

from typing import (
    Any,
)

from tuya_iot.device import (
    SmartHomeDeviceManage,
    IndustrySolutionDeviceManage,
)


class XTSmartHomeDeviceManage(SmartHomeDeviceManage):
    def get_device_list_info(self, device_ids: list[str]) -> dict[str, Any]:
        response = self.api.get("/v1.0/devices/", {"device_ids": ",".join(device_ids)})
        if response["success"]:
            for info in response["result"]["devices"]:
                if "status" in info:
                    info.pop("status")
        response["result"]["list"] = response["result"]["devices"]
        return response

    def get_device_list_status(self, device_ids: list[str]) -> dict[str, Any]:
        response = self.api.get("/v1.0/devices/", {"device_ids": ",".join(device_ids)})
        status_list = []
        if response["success"]:
            for info in response["result"]["devices"]:
                status_list.append({"id": info["id"], "status": info.get("status", [])})

        response["result"] = status_list
        return response


class XTIndustrySolutionDeviceManage(IndustrySolutionDeviceManage):
    pass
