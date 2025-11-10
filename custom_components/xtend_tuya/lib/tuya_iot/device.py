"""Tuya device api."""
from __future__ import annotations

import time
from abc import ABCMeta, abstractclassmethod
from types import SimpleNamespace
from typing import Any, Literal, Optional

from .openapi import TuyaOpenAPI
from .openlogging import logger
from .openmq import TuyaOpenMQ
from .tuya_enums import AuthType

PROTOCOL_DEVICE_REPORT = 4
PROTOCOL_OTHER = 20

BIZCODE_ONLINE = "online"
BIZCODE_OFFLINE = "offline"
BIZCODE_NAME_UPDATE = "nameUpdate"
BIZCODE_DPNAME_UPDATE = "dpNameUpdate"
BIZCODE_BIND_USER = "bindUser"
BIZCODE_DELETE = "delete"


class TuyaDeviceFunction(SimpleNamespace):
    """Tuya device's function.

    Attributes:
        code(str): function's code
        desc(str): function's description
        name(str): function's name
        type(str): function's type, which may be Boolean, Integer, Enum, Json
        values(dict): function's value range
    """

    code: str
    desc: str
    name: str
    type: str
    values: dict[str, Any]


class TuyaDeviceStatusRange(SimpleNamespace):
    """Tuya device's status range.

    Attributes:
        code(str): status's code
        type(str): status's type, which may be Boolean, Integer, Enum, Json
        values(dict): status's value range
    """

    code: str
    type: str
    values: str


class TuyaDevice(SimpleNamespace):
    """Tuya Device.

    https://developer.tuya.com/en/docs/iot/open-api/api-reference/smart-home-devices-management/device-management?id=K9g6rfntdz78a#title-5-Return%20parameter

    Attributes:
          id: Device id
          name: Device name
          local_key: Key
          category: Product category
          product_id: Product ID
          product_name: Product name
          sub: Determine whether it is a sub-device, true-> yes; false-> no
          uuid: The unique device identifier
          asset_id: asset id of the device
          online: Online status of the device
          icon: Device icon
          ip: Device IP
          time_zone: device time zone
          active_time: The last pairing time of the device
          create_time: The first network pairing time of the device
          update_time: The update time of device status

          status: Status set of the device
          function: Instruction set of the device
          status_range: Status value range set of the device
    """

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

    status: dict[str, Any] = {}
    function: dict[str, TuyaDeviceFunction] = {}
    status_range: dict[str, TuyaDeviceStatusRange] = {}

    def __eq__(self, other):
        """If devices are the same one."""
        return self.id == other.id


class TuyaDeviceListener(metaclass=ABCMeta):
    """Tuya device listener."""

    @abstractclassmethod
    def update_device(self, device: TuyaDevice):
        """Update device info.

        Args:
            device(TuyaDevice): updated device info
        """
        pass

    @abstractclassmethod
    def add_device(self, device: TuyaDevice):
        """Device Added.

        Args:
            device(TuyaDevice): Device added
        """
        pass

    @abstractclassmethod
    def remove_device(self, device_id: str):
        """Device removed.

        Args:
            device_id(str): device's id which removed
        """
        pass


class TuyaDeviceManager:
    """Tuya Device Manager.

    This Manager support device control, including getting device status,
    specifications, the latest statuses, and sending commands

    """

    def __init__(self, api: TuyaOpenAPI, mq: TuyaOpenMQ) -> None:
        """Tuya device manager init."""
        self.api = api
        self.mq = mq
        if api.auth_type == AuthType.SMART_HOME:
            self.device_manage = SmartHomeDeviceManage(api)
        else:
            self.device_manage = IndustrySolutionDeviceManage(api)

        mq.add_message_listener(self.on_message)
        self.device_map: dict[str, TuyaDevice] = {}
        self.device_listeners = set()

    def __del__(self):
        """Remove mqtt listener after object del."""
        self.mq.remove_message_listener(self.on_message)

    def on_message(self, msg: str):
        logger.debug(f"mq receive-> {msg}")
        protocol = msg.get("protocol", 0)
        data = msg.get("data", {})
        if protocol == PROTOCOL_DEVICE_REPORT:
            self._on_device_report(data["devId"], data["status"])
        elif protocol == PROTOCOL_OTHER:
            self._on_device_other(data["devId"], data["bizCode"], data)

    def __update_device(self, device: TuyaDevice):
        for listener in self.device_listeners:
            listener.update_device(device)

    def _on_device_report(self, device_id: str, status: list):
        device = self.device_map.get(device_id, None)
        if not device:
            return
        logger.debug(f"mq _on_device_report-> {status}")
        for item in status:
            if "code" in item and "value" in item:
                code = item["code"]
                value = item["value"]
                device.status[code] = value

        self.__update_device(device)

    def _on_device_other(self, device_id: str, biz_code: str, data: dict[str, Any]):
        logger.debug(f"mq _on_device_other-> {device_id} -- {biz_code}")

        # bind device to user
        if biz_code == BIZCODE_BIND_USER:
            device_id = data["devId"]
            device_ids = [device_id]
            # wait for es sync
            time.sleep(1)

            self._update_device_list_info_cache(device_ids)
            self._update_device_list_status_cache(device_ids)

            self.update_device_function_cache(device_ids)

            if device_id in self.device_map.keys():
                device = self.device_map.get(device_id)
                for listener in self.device_listeners:
                    listener.add_device(device)

        # device status update
        device = self.device_map.get(device_id, None)
        if not device:
            return

        if biz_code == BIZCODE_ONLINE:
            device.online = True
            self.__update_device(device)
        elif biz_code == BIZCODE_OFFLINE:
            device.online = False
            self.__update_device(device)
        elif biz_code == BIZCODE_NAME_UPDATE:
            device.name = data["bizData"]["name"]
            self.__update_device(device)
        elif biz_code == BIZCODE_DPNAME_UPDATE:
            pass
        elif biz_code == BIZCODE_DELETE:
            del self.device_map[device_id]
            for listener in self.device_listeners:
                listener.remove_device(device.id)

    ##############################
    # Memory Cache

    def update_device_list_in_smart_home(self):
        """Update devices status in project type SmartHome."""
        response = self.api.get(f"/v1.0/users/{self.api.token_info.uid}/devices")
        if response["success"]:
            for item in response["result"]:
                device = TuyaDevice(**item)
                status = {}
                for item_status in device.status:
                    if "code" in item_status and "value" in item_status:
                        code = item_status["code"]
                        value = item_status["value"]
                        status[code] = value
                device.status = status
                self.device_map[item["id"]] = device

        self.update_device_function_cache()

    def update_device_caches(self, devIds: list[str]):
        """Update devices status in cache.

        Update devices info, devices status

        Args:
          devIds(list[str]): devices' id, max 20 once call
        """
        self._update_device_list_info_cache(devIds)
        self._update_device_list_status_cache(devIds)

        self.update_device_function_cache(devIds)

    def _update_device_list_info_cache(self, devIds: list[str]):

        response = self.get_device_list_info(devIds)
        result = response.get("result", {})
        for item in result.get("list", []):
            device_id = item["id"]
            self.device_map[device_id] = TuyaDevice(**item)

    def _update_device_list_status_cache(self, devIds: list[str]):

        response = self.get_device_list_status(devIds)
        for item in response.get("result", []):
            device_id = item["id"]
            for status in item["status"]:
                if "code" in status and "value" in status:
                    code = status["code"]
                    value = status["value"]
                    device = self.device_map[device_id]
                    device.status[code] = value

    def update_device_function_cache(self, devIds: list = []):
        """Update device function cache."""
        device_map = (
            filter(lambda d: d.id in devIds, self.device_map.values())
            if devIds
            else self.device_map.values()
        )

        for device in device_map:
            response = self.get_device_specification(device.id)
            if response.get("success"):
                result = response.get("result", {})
                function_map = {}
                for function in result["functions"]:
                    code = function["code"]
                    function_map[code] = TuyaDeviceFunction(**function)

                status_range = {}
                for status in result["status"]:
                    code = status["code"]
                    status_range[code] = TuyaDeviceStatusRange(**status)

                device.function = function_map
                device.status_range = status_range

    def add_device_listener(self, listener: TuyaDeviceListener):
        """Add device listener."""
        self.device_listeners.add(listener)

    def remove_device_listener(self, listener: TuyaDeviceListener):
        """Remove device listener."""
        self.device_listeners.remove(listener)

    ##############################
    # OpenAPI

    # Device Management
    # https://developer.tuya.com/docs/cloud/industrial-general-device-management/2fed20dbd9?id=Kag2t5om665oi

    def get_device_info(self, device_id: str) -> dict[str, Any]:
        """Get device info.

        Args:
          device_id(str): device id
        """
        return self.device_manage.get_device_info(device_id)

    def get_device_list_info(self, devIds: list[str]) -> dict[str, Any]:
        """Get devices info.

        Args:
          device_id(list): device id list

        Returns:
            response: response body

        """
        return self.device_manage.get_device_list_info(devIds)

    # def updateDeviceInfo(self, device_id: str, info) -> dict[str, Any]:
    # """Update device information

    # Update device information, such as the device name.

    # Args:
    #   device_id(str): device id
    #   info(map): A dict mapping device information, for example:{"name": "room light"}

    # Returns:
    #     response: response body

    # """
    # return self.device_manage.get_device_info(device_id, info)

    def remove_device(self, device_id: str) -> dict[str, Any]:
        """Remove device.

        Args:
          device_id(str): device id

        Returns:
            response: response body
        """
        return self.device_manage.remove_device(device_id)

    def remove_device_list(self, devIds: list[str]) -> dict[str, Any]:
        """Remove devices.

        Args:
          device_id(list): device id list

        Returns:
            response: response body
        """
        return self.device_manage.remove_device_list(devIds)

    def get_factory_info(self, device_id: str) -> dict[str, Any]:
        """Get device's factory info.

        Args:
          device_id(list): device id list

        Returns:
            response: response body
        """
        return self.device_manage.get_factory_info(device_id)

    def factory_reset(self, device_id: str) -> dict[str, Any]:
        """Reset device to factory setting.

        Args:
          device_id(str): device id

        Returns:
            response: response body
        """
        return self.device_manage.factory_reset(device_id)

    # Device Status
    # https://developer.tuya.com/docs/cloud/industrial-general-device-status-query/f8108a55e3?id=Kag2t60ii54jf

    def get_device_status(self, device_id: str) -> dict[str, Any]:
        """Get device status.

        Args:
          device_id(str): device id

        Returns:
            response: response body
        """
        return self.device_manage.get_device_status(device_id)

    def get_device_list_status(self, devIds: list[str]) -> dict[str, Any]:
        """Get devices status.

        Args:
          devIds(list): device ids

        Returns:
            response: response body
        """
        return self.device_manage.get_device_list_status(devIds)

    # Device Control
    # https://developer.tuya.com/docs/cloud/industrial-general-device-control/5d2e6fbe8e?id=Kag2t6n3ony2c

    def get_device_functions(self, device_id: str) -> dict[str, Any]:
        """Get the Instruction set supported by the device.

        Get the Instruction set supported by the device based on the device ID.

        Args:
          device_id: device id

        Returns:
            response: response body
        """
        return self.device_manage.get_device_functions(device_id)

    def get_category_functions(self, categoryId: str) -> dict[str, Any]:
        """Get the instruction set supported by the category.

        Get the instruction set supported by the category based on the product category Code

        Args:
          category: category code

        Returns:
            response: response body
        """
        return self.device_manage.get_category_functions(categoryId)

    def get_device_specification(self, device_id: str) -> dict[str, str]:
        """Get device specification attributes.

        Obtain device specification attributes according to device ID, including command set and status set.

        Args:
          device_id: device id

        Returns:
            response: response body
        """
        return self.device_manage.get_device_specification(device_id)

    def send_commands(
        self, device_id: str, commands: list[dict[str, Any]]
    ) -> dict[str, Any]:

        """Send commands.

        Send command to the device.For example:
          {"commands": [{"code": "switch_led","value": true}]}

        Args:
          device_id(str): device id
          commands(list):  commands list

        Returns:
            response: response body
        """
        return self.device_manage.send_commands(device_id, commands)

    ##############################

    def get_device_stream_allocate(
        self, device_id: str, stream_type: Literal["flv", "hls", "rtmp", "rtsp"]
    ) -> Optional[str]:
        """Get the live streaming address by device ID and the video type.

        These live streaming video protocol types are available: RTSP, HLS, FLV, and RTMP.

        Args:
          device_id(str): device id
          stream_type(str): type of stream

        Returns:
            None or URL to the requested stream
        """
        return self.device_manage.get_device_stream_allocate(device_id, stream_type)


class DeviceManage(metaclass=ABCMeta):
    api: TuyaOpenAPI

    def __init__(self, api: TuyaOpenAPI):
        self.api = api

    @abstractclassmethod
    def update_device_caches(self, devIds: list[str]):
        pass

    @abstractclassmethod
    def get_device_info(self, device_id: str) -> dict[str, Any]:
        pass

    @abstractclassmethod
    def get_device_list_info(self, devIds: list[str]) -> dict[str, Any]:
        pass

    @abstractclassmethod
    def get_device_status(self, device_id: str) -> dict[str, Any]:
        pass

    @abstractclassmethod
    def get_device_list_status(self, devIds: list[str]) -> dict[str, Any]:
        pass

    @abstractclassmethod
    def get_factory_info(self, device_id: str) -> dict[str, Any]:
        pass

    @abstractclassmethod
    def factory_reset(self, device_id: str) -> dict[str, Any]:
        pass

    @abstractclassmethod
    def remove_device(self, device_id: str) -> dict[str, Any]:
        pass

    @abstractclassmethod
    def remove_device_list(self, devIds: list[str]) -> dict[str, Any]:
        pass

    @abstractclassmethod
    def get_device_functions(self, device_id: str) -> dict[str, Any]:
        pass

    @abstractclassmethod
    def get_category_functions(self, categoryId: str) -> dict[str, Any]:
        pass

    @abstractclassmethod
    def get_device_specification(self, device_id: str) -> dict[str, str]:
        pass

    @abstractclassmethod
    def get_device_stream_allocate(
        self, device_id: str, stream_type: Literal["flv", "hls", "rtmp", "rtsp"]
    ) -> Optional[str]:
        pass

    @abstractclassmethod
    def send_commands(self, device_id: str, commands: list[str]) -> dict[str, Any]:
        pass


class SmartHomeDeviceManage(DeviceManage):
    def update_device_caches(self, devIds: list[str]):
        pass

    def get_device_info(self, device_id: str) -> dict[str, Any]:
        response = self.api.get(f"/v1.0/devices/{device_id}")
        response["result"].pop("status")
        return response

    def get_device_list_info(self, device_ids: list[str]) -> dict[str, Any]:
        response = self.api.get("/v1.0/devices/", {"device_ids": ",".join(device_ids)})
        if response["success"]:
            for info in response["result"]["devices"]:
                info.pop("status")
        response["result"]["list"] = response["result"]["devices"]
        return response

    def get_device_status(self, device_id: str) -> dict[str, Any]:
        response = self.api.get(f"/v1.0/devices/{device_id}")
        response["result"] = response["result"]["status"]
        return response

    def get_device_list_status(self, device_ids: list[str]) -> dict[str, Any]:
        response = self.api.get("/v1.0/devices/", {"device_ids": ",".join(device_ids)})
        status_list = []
        if response["success"]:
            for info in response["result"]["devices"]:
                status_list.append({"id": info["id"], "status": info["status"]})

        response["result"] = status_list
        return response

    def get_factory_info(self, devIds: str) -> dict[str, Any]:
        return self.api.get(
            "/v1.0/devices/factory-infos", {"device_ids": ",".join(devIds)}
        )

    def factory_reset(self, device_id: str) -> dict[str, Any]:
        return self.api.post(f"/v1.0/devices/{device_id}/reset-factory")

    def remove_device(self, device_id: str) -> dict[str, Any]:
        return self.api.delete(f"/v1.0/devices/{device_id}")

    def remove_device_list(self, devIds: list[str]) -> dict[str, Any]:
        raise Exception("Api not support.")

    def get_device_functions(self, device_id: str) -> dict[str, Any]:
        return self.api.get(f"/v1.0/devices/{device_id}/functions")

    def get_category_functions(self, categoryId: str) -> dict[str, Any]:
        return self.api.get(f"/v1.0/functions/{categoryId}")

    # https://developer.tuya.com/en/docs/cloud/device-control?id=K95zu01ksols7#title-27-Get%20the%20specifications%20and%20properties%20of%20the%20device%2C%20including%20the%20instruction%20set%20and%20status%20set
    def get_device_specification(self, device_id: str) -> dict[str, str]:
        return self.api.get(f"/v1.0/devices/{device_id}/specifications")

    def get_device_stream_allocate(
        self, device_id: str, stream_type: Literal["flv", "hls", "rtmp", "rtsp"]
    ) -> Optional[str]:
        """Get the live streaming address by device ID and the video type.

        These live streaming video protocol types are available: RTSP, HLS, FLV, and RTMP.

        https://developer.tuya.com/en/docs/cloud/iot-video-live-stream?id=Kaiuybz0pzle4
        """
        response = self.api.post(
            f"/v1.0/devices/{device_id}/stream/actions/allocate", {"type": stream_type}
        )
        if response["success"]:
            return response["result"]["url"]
        return None

    def send_commands(
        self, device_id: str, commands: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return self.api.post(
            f"/v1.0/devices/{device_id}/commands", {"commands": commands}
        )


class IndustrySolutionDeviceManage(DeviceManage):
    def update_device_caches(self, devIds: list[str]):
        pass

    def get_device_info(self, device_id: str) -> dict[str, Any]:
        return self.api.get(f"/v1.0/iot-03/devices/{device_id}")

    def get_device_list_info(self, device_ids: list[str]) -> dict[str, Any]:
        return self.api.get(
            "/v1.0/iot-03/devices", {"device_ids": ",".join(device_ids)}
        )

    def get_device_status(self, device_id: str) -> dict[str, Any]:
        return self.api.get(f"/v1.0/iot-03/devices/{device_id}/status")

    def get_device_list_status(self, devIds: list[str]) -> dict[str, Any]:
        return self.api.get(
            "/v1.0/iot-03/devices/status", {"device_ids": ",".join(devIds)}
        )

    def get_factory_info(self, device_id: str) -> dict[str, Any]:
        return self.api.get("/v1.0/iot-03/devices/factory-infos", device_id)

    def factory_reset(self, device_id: str) -> dict[str, Any]:
        return self.api.delete(f"/v1.0/iot-03/devices/{device_id}/actions/reset")

    def remove_device(self, device_id: str) -> dict[str, Any]:
        return self.api.delete(f"/v1.0/iot-03/devices/{device_id}")

    def remove_device_list(self, device_ids: list[str]) -> dict[str, Any]:
        return self.api.delete(
            "/v1.0/iot-03/devices", {"device_ids": ",".join(device_ids)}
        )

    def get_device_functions(self, device_id: str) -> dict[str, Any]:
        return self.api.get(f"/v1.0/iot-03/devices/{device_id}/functions")

    def get_category_functions(self, categoryId: str) -> dict[str, Any]:
        return self.api.get(f"/v1.0/iot-03/categories/{categoryId}/functions")

    # https://developer.tuya.com/en/docs/cloud/device-control?id=K95zu01ksols7#title-27-Get%20the%20specifications%20and%20properties%20of%20the%20device%2C%20including%20the%20instruction%20set%20and%20status%20set
    def get_device_specification(self, device_id: str) -> dict[str, str]:
        return self.api.get(f"/v1.0/iot-03/devices/{device_id}/specification")

    def get_device_stream_allocate(
        self, device_id: str, stream_type: Literal["flv", "hls", "rtmp", "rtsp"]
    ) -> Optional[str]:
        """Get the live streaming address by device ID and the video type.

        Not implemented for this device manager.
        """
        return None

    def send_commands(
        self, device_id: str, commands: list[dict[str, Any]]
    ) -> dict[str, Any]:

        return self.api.post(
            f"/v1.0/iot-03/devices/{device_id}/commands", {"commands": commands}
        )
