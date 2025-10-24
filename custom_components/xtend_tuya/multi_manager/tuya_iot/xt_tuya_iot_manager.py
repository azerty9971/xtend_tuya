"""
This file contains all the code that inherit from IOT sdk from Tuya:
https://github.com/tuya/tuya-iot-python-sdk
"""

from __future__ import annotations
import json
import datetime
import time
from tuya_iot import (
    TuyaDeviceManager,
    TuyaOpenMQ,
)
from tuya_iot.device import (
    BIZCODE_BIND_USER,
)
from tuya_iot.tuya_enums import (
    AuthType,
)
from typing import Any, cast
from ...const import (
    LOGGER,
    MESSAGE_SOURCE_TUYA_IOT,
    XTDeviceSourcePriority,
    XTDPCode,
    XTIRHubInformation,
    XTIRRemoteInformation,
    XTIRRemoteKeysInformation,
)
from ..shared.shared_classes import (
    XTDevice,
    XTDeviceFunction,
    XTDeviceStatusRange,
    XTDeviceMap,
)
from ..shared.threading import (
    XTConcurrencyManager,
    XTEventLoopProtector,
)
from ..shared.merging_manager import (
    XTMergingManager,
)
from ..multi_manager import (
    MultiManager,  # noqa: F811
)
from ...entity import XTEntity
from .ipc.xt_tuya_iot_ipc_manager import XTIOTIPCManager
from .xt_tuya_iot_openapi import (
    XTIOTOpenAPI,
)
from .xt_tuya_iot_device import (
    XTIndustrySolutionDeviceManage,
    XTSmartHomeDeviceManage,
)


class XTIOTDeviceManager(TuyaDeviceManager):
    device_map: XTDeviceMap = XTDeviceMap({}, XTDeviceSourcePriority.TUYA_IOT)

    def __init__(
        self,
        multi_manager: MultiManager,
        api: XTIOTOpenAPI,
        non_user_api: XTIOTOpenAPI,
        mq: TuyaOpenMQ,
    ) -> None:
        super().__init__(api, mq)
        if api.auth_type == AuthType.SMART_HOME:
            self.device_manage = XTSmartHomeDeviceManage(api)
        else:
            self.device_manage = XTIndustrySolutionDeviceManage(api)
        self.device_map = XTDeviceMap({}, XTDeviceSourcePriority.TUYA_IOT)  # type: ignore
        mq.remove_message_listener(self.on_message)
        mq.add_message_listener(self.forward_message_to_multi_manager)  # type: ignore
        self.multi_manager = multi_manager
        self.ipc_manager = XTIOTIPCManager(api, multi_manager)
        self.non_user_api = non_user_api
        self.api = api

    def forward_message_to_multi_manager(self, msg: dict):
        self.multi_manager.on_message(MESSAGE_SOURCE_TUYA_IOT, msg)

    def get_device_info(self, device_id: str) -> dict[str, Any]:
        """Get device info.

        Args:
          device_id(str): device id
        """
        try:
            return self.device_manage.get_device_info(device_id)
        except Exception as e:
            LOGGER.warning(f"get_device_info failed, trying other method {e}")
            response = self.api.get(f"/v2.0/cloud/thing/{device_id}")
            if response["success"]:
                result = response["result"]
                result["online"] = result["is_online"]
                return response
        return {}

    def get_device_status(self, device_id: str) -> dict[str, Any]:
        """Get device status.

        Args:
          device_id(str): device id

        Returns:
            response: response body
        """
        try:
            return self.device_manage.get_device_status(device_id)
        except Exception as e:
            LOGGER.warning(f"get_device_status failed, trying other method {e}")
            response = self.api.get(f"/v1.0/iot-03/devices/{device_id}/status")
            if response["success"]:
                return response
        return {}

    async def async_update_device_list_in_smart_home_mod(self):
        if self.api.token_info is None:  # CHANGED
            return None  # CHANGED
        response = await XTEventLoopProtector.execute_out_of_event_loop_and_return(
            self.api.get, f"/v1.0/users/{self.api.token_info.uid}/devices"
        )
        if response["success"]:
            for item in response["result"]:
                device = XTDevice(**item)  # CHANGED
                device.source = "IOT update_device_list_in_smart_home_mod"  # CHANGED
                status = {}
                for item_status in device.status:
                    if "code" in item_status and "value" in item_status:
                        code = item_status["code"]  # type: ignore
                        value = item_status["value"]  # type: ignore
                        status[code] = value
                device.status = status
                self.device_map[device.id] = device  # CHANGED
                if "id" not in item:
                    LOGGER.warning(f"Received invalid device info: {item}")

        # ADDED
        for device in self.multi_manager.devices_shared.values():
            if device.id not in self.device_map:
                self.device_map[device.id] = device
        # END ADDED

        await self.async_update_device_function_cache()

    # Copy of the Tuya original method with some minor modifications
    def update_device_list_in_smart_home_mod(self):
        if self.api.token_info is None:  # CHANGED
            return None  # CHANGED
        response = self.api.get(f"/v1.0/users/{self.api.token_info.uid}/devices")
        if response["success"]:
            for item in response["result"]:
                device = XTDevice(**item)  # CHANGED
                device.source = "IOT update_device_list_in_smart_home_mod"  # CHANGED
                status = {}
                for item_status in device.status:
                    if "code" in item_status and "value" in item_status:
                        code = item_status["code"]  # type: ignore
                        value = item_status["value"]  # type: ignore
                        status[code] = value
                device.status = status
                self.device_map[device.id] = device  # CHANGED
                if "id" not in item:
                    LOGGER.warning(f"Received invalid device info: {item}")

        # ADDED
        for device in self.multi_manager.devices_shared.values():
            if device.id not in self.device_map:
                self.device_map[device.id] = device
        # END ADDED

        self.update_device_function_cache()

    async def async_update_device_caches(self, devIds: list[str]):
        """Update devices status in cache.

        Update devices info, devices status

        Args:
          devIds(list[str]): devices' id, max 20 once call
        """
        self._update_device_list_info_cache(devIds)
        self._update_device_list_status_cache(devIds)

        self.update_device_function_cache(devIds)

    def get_devices_from_sharing(self) -> dict[str, XTDevice]:
        return_dict: dict[str, XTDevice] = {}
        if self.api.token_info is None:
            return {}
        response = self.api.get(
            f"/v1.0/users/{self.api.token_info.uid}/devices?from=sharing"
        )
        if response["success"]:
            for item in response["result"]:
                device = XTDevice(**item)
                device.source = "IOT get_devices_from_sharing"
                status = {}
                for item_status in device.status:
                    if "code" in item_status and "value" in item_status:
                        code = item_status["code"]  # type: ignore
                        value = item_status["value"]  # type: ignore
                        status[code] = value
                device.status = status
                return_dict[item["id"]] = device
        return return_dict

    async def async_update_device_list_in_smart_home(self):
        await self.async_update_device_list_in_smart_home_mod()

    def update_device_list_in_smart_home(self):
        self.update_device_list_in_smart_home_mod()

    async def async_update_device_function_cache(self, devIds: list = []):
        concurrency_manager = XTConcurrencyManager(max_concurrency=9)

        device_map = (
            filter(lambda d: d.id in devIds, self.device_map.values())
            if devIds
            else self.device_map.values()
        )

        async def update_single_device(device: XTDevice):
            await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                self.update_device_function_cache, [device.id]
            )

        for device in device_map:
            concurrency_manager.add_coroutine(update_single_device(device))
        await concurrency_manager.gather()

    def update_device_function_cache(self, devIds: list = []):
        device_map = (
            filter(lambda d: d.id in devIds, self.device_map.values())
            if devIds
            else self.device_map.values()
        )
        LOGGER.warning(f"update_device_function_cache: {device_map}")

        for device in device_map:
            super().update_device_function_cache(devIds=[device.id])

        for device in device_map:
            device_open_api = self.get_open_api_device(device)
            self.multi_manager.device_watcher.report_message(device.id, f"device_open_api: {device_open_api}", device)
            # self.multi_manager.device_watcher.report_message(device_id, f"About to merge {device}\r\n\r\nand\r\n\r\n{device_open_api}", device)
            XTMergingManager.merge_devices(device, device_open_api, self.multi_manager)
            self.multi_manager.device_watcher.report_message(device.id, f"After merge: {device_open_api}", device)
            self.multi_manager.virtual_state_handler.apply_init_virtual_states(device)
            self.multi_manager.device_watcher.report_message(device.id, f"after virtual states: {device_open_api}", device)

    def on_message(self, msg: str):
        super().on_message(msg)

    def _on_device_other(self, device_id: str, biz_code: str, data: dict[str, Any]):
        self.multi_manager.device_watcher.report_message(
            device_id,
            f"[{MESSAGE_SOURCE_TUYA_IOT}]On device other: {biz_code} <=> {data}",
        )
        if biz_code == BIZCODE_BIND_USER:
            self.multi_manager.add_device_by_id(data["devId"])
            return None

        return super()._on_device_other(device_id, biz_code, data)

    def add_device_by_id(self, device_id: str):
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

    def _on_device_report(self, device_id: str, status: list):
        self.multi_manager.device_watcher.report_message(
            device_id, f"[{MESSAGE_SOURCE_TUYA_IOT}]On device report: {status}"
        )
        device = self.device_map.get(device_id, None)
        if not device:
            return
        status_new = self.multi_manager.convert_device_report_status_list(
            device_id, status
        )
        status_new = self.multi_manager.multi_source_handler.filter_status_list(
            device_id, MESSAGE_SOURCE_TUYA_IOT, status_new
        )
        status_new = self.multi_manager.virtual_state_handler.apply_virtual_states_to_status_list(
            device, status_new, MESSAGE_SOURCE_TUYA_IOT
        )
        for item in status_new:
            if "code" in item and "value" in item:
                code = item["code"]
                value = item["value"]
                device.status[code] = value

        super()._on_device_report(device_id, [])

    def _update_device_list_info_cache(self, devIds: list[str]):
        response = self.get_device_list_info(devIds)
        result = response.get("result", {})
        for item in result.get("list", []):
            device_id = item["id"]
            self.device_map[device_id] = XTDevice(**item)
            self.device_map[device_id].source = "IOT _update_device_list_info_cache"

    def get_open_api_device(self, device: XTDevice) -> XTDevice | None:
        device_properties = XTDevice.from_compatible_device(
            device, "IOT get_open_api_device"
        )
        device_properties.function = {}
        device_properties.status_range = {}
        device_properties.status = {}
        device_properties.local_strategy = {}
        device_properties.device_source_priority = XTDeviceSourcePriority.TUYA_IOT
        response = self.api.get(f"/v2.0/cloud/thing/{device.id}/shadow/properties")
        response2 = self.api.get(f"/v2.0/cloud/thing/{device.id}/model")
        if not response.get("success") or not response2.get("success"):
            LOGGER.warning(f"Response1: {response}")
            LOGGER.warning(f"Response2: {response2}")
            return

        if response2.get("success"):
            result = response2.get("result", {})
            data_model = json.loads(result.get("model", "{}"))
            device_properties.data_model = data_model
            for service in data_model["services"]:
                for property in service["properties"]:
                    if (
                        "abilityId" in property
                        and "code" in property
                        and "accessMode" in property
                        and "typeSpec" in property
                    ):
                        dp_id = int(property["abilityId"])
                        code = property["code"]
                        typeSpec = property["typeSpec"]
                        real_type = XTEntity.determine_dptype(typeSpec["type"])
                        access_mode = property["accessMode"]
                        typeSpec.pop("type")
                        typeSpec_json = json.dumps(typeSpec)
                        if dp_id not in device_properties.local_strategy:
                            if (
                                code in device_properties.function
                                or code in device_properties.status_range
                            ):
                                property_update = False
                            else:
                                property_update = True
                            device_properties.local_strategy[dp_id] = {
                                "value_convert": "default",
                                "status_code": code,
                                "config_item": {
                                    "statusFormat": f'{{"{code}":"$"}}',
                                    "valueDesc": typeSpec_json,
                                    "valueType": real_type,
                                    "pid": device.product_id,
                                },
                                "property_update": property_update,
                                "use_open_api": True,
                                "access_mode": access_mode,
                                "status_code_alias": [],
                            }
                            if code in device_properties.status_range:
                                device_properties.status_range[code].dp_id = dp_id
                            if code in device_properties.function:
                                device_properties.function[code].dp_id = dp_id

        if response.get("success"):
            result = response.get("result", {})
            for dp_property in result["properties"]:
                if "dp_id" not in dp_property:
                    continue
                dp_id = int(dp_property["dp_id"])
                if "dp_id" in dp_property and "type" in dp_property:
                    code = dp_property["code"]
                    dp_type = dp_property.get("type", None)
                    if dp_id not in device_properties.local_strategy:
                        if (
                            code in device_properties.function
                            or code in device_properties.status_range
                        ):
                            property_update = False
                        else:
                            property_update = True
                        real_type = XTEntity.determine_dptype(dp_type)
                        device_properties.local_strategy[dp_id] = {
                            "value_convert": "default",
                            "status_code": code,
                            "config_item": {
                                "statusFormat": f'{{"{code}":"$"}}',
                                "valueDesc": "{}",
                                "valueType": real_type,
                                "pid": device.product_id,
                            },
                            "property_update": property_update,
                            "use_open_api": True,
                            "status_code_alias": [],
                        }
                if (
                    "code" in dp_property
                    and "dp_id" in dp_property
                    and dp_id in device_properties.local_strategy
                ):
                    code = dp_property["code"]
                    if (
                        code not in device_properties.status_range
                        and code not in device_properties.function
                    ):
                        if "access_mode" in device_properties.local_strategy[
                            dp_id
                        ] and device_properties.local_strategy[dp_id][
                            "access_mode"
                        ] in [
                            "rw",
                            "wr",
                        ]:
                            device_properties.function[code] = XTDeviceFunction(
                                code=code,
                                type=device_properties.local_strategy[dp_id][
                                    "config_item"
                                ]["valueType"],
                                values=device_properties.local_strategy[dp_id][
                                    "config_item"
                                ]["valueDesc"],
                                dp_id=dp_id,
                            )
                        else:
                            device_properties.status_range[code] = XTDeviceStatusRange(
                                code=code,
                                type=device_properties.local_strategy[dp_id][
                                    "config_item"
                                ]["valueType"],
                                values=device_properties.local_strategy[dp_id][
                                    "config_item"
                                ]["valueDesc"],
                                dp_id=dp_id,
                            )
                    if code not in device_properties.status:
                        device_properties.status[code] = dp_property.get("value", None)
        # self.multi_manager.device_watcher.report_message(device_properties.id, f"get_open_api_device: {device}", device_properties)
        return device_properties

    def send_property_update(self, device_id: str, properties: list[dict[str, Any]]):
        for property in properties:
            for prop_key in property:
                property_str = json.dumps({prop_key: property[prop_key]})
                self.multi_manager.device_watcher.report_message(
                    device_id,
                    f"Sending property update, payload: {json.dumps({'properties': property_str})}",
                )
                self.api.post(
                    f"/v2.0/cloud/thing/{device_id}/shadow/properties/issue",
                    {"properties": property_str},
                )

    def send_lock_unlock_command(self, device: XTDevice, lock: bool) -> bool:
        self.multi_manager.device_watcher.report_message(
            device.id, f"Sending lock/unlock command open: {open}"
        )
        return self.send_lock_unlock_command_multi_api(device, lock)

    def send_lock_unlock_command_multi_api(
        self, device: XTDevice, lock: bool, api: XTIOTOpenAPI | None = None
    ) -> bool:
        if api is None:
            if self.send_lock_unlock_command_multi_api(device, lock, self.non_user_api):
                return True
            else:
                return self.send_lock_unlock_command_multi_api(device, lock, self.api)
        if lock:
            open = "false"
        else:
            open = "true"
        supported_unlock_types = self.get_supported_unlock_types(device, api)
        if "remoteUnlockWithoutPwd" in supported_unlock_types:
            if self.call_door_operate(device, open, api):
                return True
            if lock:
                # Locking of the door
                pass
            else:
                # Unlocking of the door
                if self.call_door_open(device, api):
                    return True
        if manual_unlock_code := cast(
            list[XTDPCode],
            device.get_preference(
                XTDevice.XTDevicePreference.LOCK_MANUAL_UNLOCK_COMMAND
            ),
        ):
            commands: list[dict[str, Any]] = []
            for dpcode in manual_unlock_code:
                if status_value := device.status.get(dpcode):
                    if not isinstance(status_value, bool):
                        commands.append({"code": dpcode, "value": status_value})
                    else:
                        commands.append({"code": dpcode, "value": not lock})
                else:
                    commands.append({"code": dpcode, "value": not lock})
            self.multi_manager.send_commands(device_id=device.id, commands=commands)
            return True  # Assume that the command worked...
        return False

    def test_lock_api_subscription(
        self, device: XTDevice, api: XTIOTOpenAPI | None = None
    ) -> bool:
        if api is None:
            if self.test_lock_api_subscription(device, self.api):
                if self.test_lock_api_subscription(device, self.non_user_api):
                    return True
            return False
        ticket = api.post(f"/v1.0/devices/{device.id}/door-lock/password-ticket")
        if code := ticket.get("code", None):
            if code == 28841101:
                return False
        return True

    def test_camera_api_subscription(
        self, device: XTDevice, api: XTIOTOpenAPI | None = None
    ) -> bool:
        if api is None:
            if self.test_camera_api_subscription(device, self.api):
                if self.test_camera_api_subscription(device, self.non_user_api):
                    return True
            return False
        ticket = api.get(f"/v1.0/devices/{device.id}/webrtc-configs")
        if code := ticket.get("code", None):
            if code == 28841106:
                return False
        return True

    def test_ir_api_subscription(
        self, device: XTDevice, api: XTIOTOpenAPI | None = None
    ) -> bool:
        if api is None:
            if self.test_ir_api_subscription(device, self.api):
                if self.test_ir_api_subscription(device, self.non_user_api):
                    return True
            return False
        ticket = api.get(f"/v2.0/infrareds/{device.id}/remotes")
        if code := ticket.get("code", None):
            if code == 28841105:
                return False
        return True

    def get_ir_hub_information(
        self, device: XTDevice, api: XTIOTOpenAPI | None = None
    ) -> XTIRHubInformation | None:
        if api is None:
            api = self.api
        remote_list = api.get(f"/v2.0/infrareds/{device.id}/remotes")
        if remote_list.get("success", False) is False:
            return None
        device_information_results: list[dict] = remote_list.get("result", [])
        device_information: XTIRHubInformation = XTIRHubInformation(
            device_id=device.id, remote_ids=[]
        )
        for remote_info_dict in device_information_results:
            brand_id: int | None = remote_info_dict.get("brand_id")
            brand_name: str = remote_info_dict.get("brand_name", "")
            category_id: int | None = remote_info_dict.get("category_id")
            remote_id: str | None = remote_info_dict.get("remote_id")
            remote_index: int = remote_info_dict.get("remote_index", 0)
            remote_name: str = remote_info_dict.get("remote_name", "")
            if brand_id is None or category_id is None or remote_id is None:
                continue
            remote_information = XTIRRemoteInformation(
                brand_id=brand_id,
                brand_name=brand_name,
                category_id=category_id,
                remote_id=remote_id,
                remote_index=remote_index,
                remote_name=remote_name,
                keys=[],
            )
            remote_information.keys = self._get_ir_remote_keys(
                device.id, remote_id, api
            )
            device_information.remote_ids.append(remote_information)
        return device_information

    def _get_ir_remote_keys(
        self, hub_id: str, remote_id: str, api: XTIOTOpenAPI
    ) -> list[XTIRRemoteKeysInformation]:
        return_list: list[XTIRRemoteKeysInformation] = []
        remote_keys = api.get(f"/v2.0/infrareds/{hub_id}/remotes/{remote_id}/keys")
        if remote_keys.get("success", False) is False:
            return return_list
        learning_codes = api.get(
            f"/v2.0/infrareds/{hub_id}/remotes/{remote_id}/learning-codes"
        )
        learning_codes_dict: dict[int, dict[str, Any]] = {}
        if learning_codes.get("success", False):
            learning_code_results: list[dict] = learning_codes.get("result", [])
            for learning_code_result_dict in learning_code_results:
                if learning_code_id := learning_code_result_dict.get("id"):
                    learning_codes_dict[learning_code_id] = learning_code_result_dict
        remote_keys_results: dict = remote_keys.get("result", {})
        remote_keys_key_list: list[dict] = remote_keys_results.get("key_list", [])
        for remote_key_dict in remote_keys_key_list:
            key: str | None = remote_key_dict.get("key")
            key_id: int | None = remote_key_dict.get("key_id")
            key_name: str | None = remote_key_dict.get("key_name")
            standard_key: bool | None = remote_key_dict.get("standard_key")
            learn_id: int | None = None
            code: str | None = None
            if key_id in learning_codes_dict:
                learn_id = learning_codes_dict[key_id].get("learn_id")
                code = learning_codes_dict[key_id].get("code")
            if (
                key is None
                or key_id is None
                or key_name is None
                or standard_key is None
            ):
                continue
            key_information = XTIRRemoteKeysInformation(
                key=key,
                key_id=key_id,
                key_name=key_name,
                standard_key=standard_key,
                learn_id=learn_id,
                code=code,
            )
            return_list.append(key_information)
        return return_list

    def send_ir_command(
        self,
        device: XTDevice,
        key: XTIRRemoteKeysInformation,
        remote: XTIRRemoteInformation,
        hub: XTIRHubInformation,
        api: XTIOTOpenAPI | None = None,
    ) -> bool:
        if api is None:
            api = self.api
        payload: dict[str, Any] = {
            "category_id": remote.category_id,
            "key_id": key.key_id,
            "key": key.key,
        }
        ir_command = api.post(
            f"/v2.0/infrareds/{hub.device_id}/remotes/{remote.remote_id}/raw/command",
            payload,
        )
        if ir_command.get("success", False) and ir_command.get("result", False):
            return True
        return False

    def delete_ir_key(
        self,
        device: XTDevice,
        key: XTIRRemoteKeysInformation,
        remote: XTIRRemoteInformation,
        hub: XTIRHubInformation,
        api: XTIOTOpenAPI | None = None,
    ) -> bool:
        if api is None:
            api = self.api
        delete_ir_command = api.delete(
            f"/v2.0/infrareds/{hub.device_id}/learning-codes/{key.learn_id}",
        )
        if delete_ir_command.get("success", False) and delete_ir_command.get(
            "result", False
        ):
            return True
        return False

    def get_ir_category_list(
        self, infrared_device: XTDevice, api: XTIOTOpenAPI | None = None
    ) -> dict[int, str]:
        if api is None:
            api = self.api
        return_dict: dict[int, str] = {}
        category_response = api.get(f"/v2.0/infrareds/{infrared_device.id}/categories")
        if category_response.get("success", False) is False:
            return {}
        category_list: list[dict[str, Any]] = category_response.get("result", [])
        for category in category_list:
            try:
                id = int(category.get("category_id", 0))
                name = str(category.get("category_name"))
                return_dict[id] = name
            except Exception:
                continue
        return return_dict

    def get_ir_brand_list(
        self,
        infrared_device: XTDevice,
        category_id: int,
        api: XTIOTOpenAPI | None = None,
    ) -> dict[int, str]:
        if api is None:
            api = self.api
        return_dict: dict[int, str] = {}
        brand_response = api.get(
            f"/v2.0/infrareds/{infrared_device.id}/categories/{category_id}/brands"
        )
        if brand_response.get("success", False) is False:
            return {}
        category_list: list[dict[str, Any]] = brand_response.get("result", [])
        for brand in category_list:
            try:
                id = int(brand.get("brand_id", 0))
                name = str(brand.get("brand_name"))
                return_dict[id] = name
            except Exception:
                continue
        return return_dict

    def create_ir_device(
        self,
        device: XTDevice,
        remote_name: str,
        category_id: int,
        brand_id: int,
        brand_name: str,
        api: XTIOTOpenAPI | None = None,
    ) -> str | None:
        if api is None:
            api = self.api
        ir_device_create_response = api.post(
            f"/v2.0/infrareds/{device.id}/remotes",
            {
                "category_id": category_id,
                "remote_name": remote_name,
                "brand_id": brand_id,
                "brand_name": brand_name,
                "remote_index": int(datetime.datetime.now().timestamp()),
            },
        )
        if ir_device_create_response.get("success", False) is True:
            new_device_id = ir_device_create_response.get("result")
            if new_device_id is not None:
                return new_device_id
        return None

    def learn_ir_key(
        self,
        device: XTDevice,
        remote: XTIRRemoteInformation,
        hub: XTIRHubInformation,
        key: str,
        key_name: str,
        timeout: int | None = None,
        api: XTIOTOpenAPI | None = None,
    ) -> bool:
        total_timeout: int = timeout if timeout is not None else 30
        check_interval: int = 1
        if api is None:
            api = self.api
        # Set device in learning mode
        learning_mode = api.put(
            f"/v2.0/infrareds/{hub.device_id}/learning-state",
            {"state": True},
        )
        if (
            learning_mode.get("success", False) is False
            or learning_mode.get("t") is None
        ):
            LOGGER.warning(f"Could not put IR Hub {device.name} in learning mode")
            return False
        learning_time = int(learning_mode["t"])
        learned_code_value: str | None = None
        for _ in range(total_timeout):
            learned_code = api.get(
                f"/v2.0/infrareds/{hub.device_id}/learning-codes",
                {"learning_time": learning_time},
            )
            if result := learned_code.get("result", {}):
                if result.get("success", False):
                    learned_code_value = result.get("code")
                    break
            time.sleep(check_interval)

        learning_mode = api.put(
            f"/v2.0/infrareds/{hub.device_id}/learning-state", {"state": False}
        )

        if learned_code_value is None:
            return False

        save_result = api.put(
            f"/v2.0/infrareds/{hub.device_id}/remotes/{remote.remote_id}/learning-codes",
            {
                "category_id": remote.category_id,
                # "brand_name": remote.brand_name,
                # "remote_name": remote.remote_name,
                "codes": [
                    {
                        # "category_id": remote.category_id,
                        "key_name": key_name,
                        "key": key,
                        "code": learned_code_value,
                        "id": learning_time // 1000,
                    }
                ],
            },
        )
        if save_result.get("success", False):
            return True
        return False

    def get_supported_unlock_types(
        self, device: XTDevice, api: XTIOTOpenAPI
    ) -> list[str]:
        supported_unlock_types: list[str] = []
        api_to_use = cast(
            XTIOTOpenAPI,
            device.get_preference(
                f"{MESSAGE_SOURCE_TUYA_IOT}{XTDevice.XTDevicePreference.LOCK_GET_SUPPORTED_UNLOCK_TYPES}",
                api,
            ),
        )
        remote_unlock_types = api_to_use.get(
            f"/v1.0/devices/{device.id}/door-lock/remote-unlocks"
        )
        self.multi_manager.device_watcher.report_message(
            device.id, f"API remote unlock types: {remote_unlock_types}"
        )
        if remote_unlock_types.get("success", False):
            device.set_preference(
                f"{MESSAGE_SOURCE_TUYA_IOT}{XTDevice.XTDevicePreference.LOCK_GET_SUPPORTED_UNLOCK_TYPES}",
                api_to_use,
            )
            results: list[dict] = remote_unlock_types.get("result", [])
            for result in results:
                if result.get("open", False):
                    if supported_unlock_type := result.get("remote_unlock_type", None):
                        supported_unlock_types.append(supported_unlock_type)
        return supported_unlock_types

    def get_door_lock_password_ticket(
        self, device: XTDevice, api: XTIOTOpenAPI
    ) -> str | None:
        api_to_use = cast(
            XTIOTOpenAPI,
            device.get_preference(
                f"{MESSAGE_SOURCE_TUYA_IOT}{XTDevice.XTDevicePreference.LOCK_GET_DOOR_LOCK_PASSWORD_TICKET}",
                api,
            ),
        )
        ticket = api_to_use.post(f"/v1.0/devices/{device.id}/door-lock/password-ticket")
        self.multi_manager.device_watcher.report_message(
            device.id, f"API remote unlock ticket: {ticket}"
        )
        if ticket.get("success", False):
            device.set_preference(
                f"{MESSAGE_SOURCE_TUYA_IOT}{XTDevice.XTDevicePreference.LOCK_GET_DOOR_LOCK_PASSWORD_TICKET}",
                api_to_use,
            )
            result: dict[str, Any] = ticket.get("result", {})
            if ticket_id := result.get("ticket_id", None):
                return ticket_id
        return None

    def call_door_operate(self, device: XTDevice, open: str, api: XTIOTOpenAPI) -> bool:
        if ticket_id := self.get_door_lock_password_ticket(device, api):
            api_to_use = cast(
                XTIOTOpenAPI,
                device.get_preference(
                    f"{MESSAGE_SOURCE_TUYA_IOT}{XTDevice.XTDevicePreference.LOCK_CALL_DOOR_OPERATE}",
                    api,
                ),
            )
            lock_operation = api_to_use.post(
                f"/v1.0/smart-lock/devices/{device.id}/password-free/door-operate",
                {"ticket_id": ticket_id, "open": open},
            )
            self.multi_manager.device_watcher.report_message(
                device.id, f"API call_door_operate result: {lock_operation}"
            )
            if lock_operation.get("success", False):
                device.set_preference(
                    f"{MESSAGE_SOURCE_TUYA_IOT}{XTDevice.XTDevicePreference.LOCK_CALL_DOOR_OPERATE}",
                    api_to_use,
                )
                return True
        return False

    def call_door_open(self, device: XTDevice, api: XTIOTOpenAPI) -> bool:
        if ticket_id := self.get_door_lock_password_ticket(device, api):
            api_to_use = cast(
                XTIOTOpenAPI,
                device.get_preference(
                    f"{MESSAGE_SOURCE_TUYA_IOT}{XTDevice.XTDevicePreference.LOCK_CALL_DOOR_OPEN}",
                    api,
                ),
            )
            lock_operation = api.post(
                f"/v1.0/devices/{device.id}/door-lock/password-free/open-door",
                {"ticket_id": ticket_id},
            )
            self.multi_manager.device_watcher.report_message(
                device.id, f"API call_door_open result: {lock_operation}"
            )
            if lock_operation.get("success", False):
                device.set_preference(
                    f"{MESSAGE_SOURCE_TUYA_IOT}{XTDevice.XTDevicePreference.LOCK_CALL_DOOR_OPEN}",
                    api_to_use,
                )
                return True
        return False
