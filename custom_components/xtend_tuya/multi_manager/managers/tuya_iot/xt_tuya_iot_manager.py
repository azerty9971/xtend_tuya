"""
This file contains all the code that inherit from IOT sdk from Tuya:
https://github.com/tuya/tuya-iot-python-sdk
"""

from __future__ import annotations
import json
import datetime
import time
import hashlib
import hmac
from ....lib.tuya_iot import (
    TuyaDeviceManager,
)
from ....lib.tuya_iot.device import (
    BIZCODE_ONLINE,
    BIZCODE_OFFLINE,
    BIZCODE_NAME_UPDATE,
    BIZCODE_DPNAME_UPDATE,
    BIZCODE_BIND_USER,
    BIZCODE_DELETE,
    PROTOCOL_DEVICE_REPORT,
)
from ....lib.tuya_iot.tuya_enums import (
    AuthType,
)
from typing import Any, cast
from ....const import (
    LOGGER,
    MESSAGE_SOURCE_TUYA_IOT,
    XTDeviceSourcePriority,
    XTDPCode,
    XTIRHubInformation,
    XTIRRemoteInformation,
    XTIRRemoteKeysInformation,
    XTLockingMechanism,
    TUYA_TEST_API_BAD_RETURN_CODES,
    XTDeviceWatcherCategory,
    BIZCODE_EVENT_NOTIFY,
    XT_DEVICE_EVENT_NOTIFY_DPCODE,
)
from ...shared.shared_classes import (
    XTDevice,
    XTDeviceFunction,
    XTDeviceStatusRange,
    XTDeviceMap,
)
from ...shared.threading import (
    XTConcurrencyManager,
    XTEventLoopProtector,
)
from ...shared.merging_manager import (
    XTMergingManager,
)
from ...multi_manager import (
    MultiManager,  # noqa: F811
)
from .ipc.xt_tuya_iot_ipc_manager import XTIOTIPCManager
from .xt_tuya_iot_openapi import (
    XTIOTOpenAPI,
)
from .xt_tuya_iot_device import (
    XTIndustrySolutionDeviceManage,
    XTSmartHomeDeviceManage,
)
from ....ha_tuya_integration.tuya_integration_imports import (
    TuyaDPType,
)
from .xt_tuya_iot_mq import (
    XTIOTOpenMQ,
)
from .xt_tuya_iot_home_manager import (
    TuyaHomeManager,
)


class XTIOTDeviceManager(TuyaDeviceManager):
    device_map: XTDeviceMap = XTDeviceMap({}, XTDeviceSourcePriority.TUYA_IOT)

    def __init__(
        self,
        multi_manager: MultiManager,
        api: XTIOTOpenAPI,
        non_user_api: XTIOTOpenAPI,
    ) -> None:
        mq = XTIOTOpenMQ(api, self)
        super().__init__(api, mq)
        mq.start()
        mq.remove_message_listener(self.on_message)
        mq.add_message_listener(self.forward_message_to_multi_manager)
        if api.auth_type == AuthType.SMART_HOME:
            self.device_manage = XTSmartHomeDeviceManage(api)
        else:
            self.device_manage = XTIndustrySolutionDeviceManage(api)
        self.device_map = XTDeviceMap({}, XTDeviceSourcePriority.TUYA_IOT)  # type: ignore
        self.multi_manager = multi_manager
        self.ipc_manager = XTIOTIPCManager(api, multi_manager)
        self.non_user_api = non_user_api
        self.api = api
        self.mq = mq
        self.home_manager: TuyaHomeManager | None = None

    def register_home_manager(self, home_manager: TuyaHomeManager):
        self.home_manager = home_manager

    def forward_message_to_multi_manager(self, msg: dict):
        self.multi_manager.on_message(msg, MESSAGE_SOURCE_TUYA_IOT)

    def refresh_mq(self):
        self.mq.stop()
        self.mq = XTIOTOpenMQ(self.api, self)
        self.mq.add_message_listener(self.forward_message_to_multi_manager)
        self.mq.start()
        if self.home_manager is not None:
            self.home_manager.mq = self.mq

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
        if self.api.token_info.is_valid() is False:  # CHANGED
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
        if self.api.token_info.is_valid() is False:  # CHANGED
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
        if self.api.token_info.is_valid() is False:
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
        for device_id in self.device_map:
            device = self.device_map[device_id]
            if device_id in devIds or not devIds:
                super().update_device_function_cache(devIds=[device_id])
                device_open_api = self.get_open_api_device(device)
                XTMergingManager.merge_devices(
                    device, device_open_api, self.multi_manager
                )
                self.multi_manager.virtual_state_handler.apply_init_virtual_states(
                    device
                )

    def on_message(self, msg: dict):
        super().on_message(msg)

    def _on_device_other(self, device_id: str, biz_code: str, data: dict[str, Any]):
        self.multi_manager.device_watcher.report_message(
            device_id,
            f"[{MESSAGE_SOURCE_TUYA_IOT}]On device other: {biz_code=} {data=}",
            XTDeviceWatcherCategory.MQTT,
        )
        if biz_code not in [
            BIZCODE_ONLINE,
            BIZCODE_OFFLINE,
            BIZCODE_NAME_UPDATE,
            BIZCODE_DPNAME_UPDATE,
            BIZCODE_BIND_USER,
            BIZCODE_DELETE,
            BIZCODE_EVENT_NOTIFY,
        ]:
            LOGGER.warning(
                f"Received unknown BizCode type: {biz_code} with data {data}, please report this to the developer"
            )
        if biz_code == BIZCODE_BIND_USER:
            self.multi_manager.add_device_by_id(data["devId"])
            return None
        elif biz_code == BIZCODE_EVENT_NOTIFY:
            data_value: dict[str, Any] = {}
            biz_data: dict[str, Any] = data.get("bizData", {})
            if event_type := biz_data.get("etype"):
                data_value["event_type"] = event_type
            if event_data := biz_data.get("edata"):
                data_value["event_data"] = event_data
            if event_time := data.get("ts"):
                data_value["event_time"] = event_time
            if data_value and event_time is not None:
                self.multi_manager.on_message(
                    msg={
                        "protocol": PROTOCOL_DEVICE_REPORT,
                        "data": {
                            "devId": device_id,
                            "status": [
                                {
                                    "code": str(XT_DEVICE_EVENT_NOTIFY_DPCODE),
                                    "t": event_time,
                                    "value": json.dumps(data_value),
                                }
                            ],
                        },
                        "t": event_time,
                    },
                    source=MESSAGE_SOURCE_TUYA_IOT,
                )
        else:
            super()._on_device_other(device_id, biz_code, data)

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

    def _on_device_report(self, device_id: str, status: list[dict[str, Any]]):
        self.multi_manager.device_watcher.report_message(
            device_id,
            f"[{MESSAGE_SOURCE_TUYA_IOT}]On device report: {status=}",
            XTDeviceWatcherCategory.MQTT,
        )
        device = self.device_map.get(device_id, None)
        if not device:
            return
        updated_status_properties = []
        dp_timestamps = {}
        status_new = self.multi_manager.convert_device_report_status_list(
            device_id,
            status,
            MESSAGE_SOURCE_TUYA_IOT,
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
                self.multi_manager.device_watcher.report_message(
                    device.id,
                    f"Status update before conversion: {code} => {value}",
                    XTDeviceWatcherCategory.STATUS_CHANGES,
                    device,
                    False,
                    code,
                )
                value = device.apply_dpcode_strategy(code, value, self.multi_manager)
                self.multi_manager.device_watcher.report_message(
                    device.id,
                    f"Status update after conversion: {code} => {value}",
                    XTDeviceWatcherCategory.STATUS_CHANGES,
                    device,
                    False,
                    code,
                )
                device.status[code] = value
                updated_status_properties.append(code)
                if t := item.get("t"):
                    dp_timestamps[code] = t

        self._update_device(
            device=device,
            updated_status_properties=updated_status_properties,
            dp_timestamps=dp_timestamps,
        )

    def _update_device(
        self,
        device: XTDevice,
        updated_status_properties: list[str] | None = None,
        dp_timestamps: dict | None = None,
    ):
        for listener in self.device_listeners:
            listener.update_device(device, updated_status_properties, dp_timestamps)

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
            LOGGER.warning(f"Response1: {response}: {device.id=}")
            LOGGER.warning(f"Response2: {response2}: {device.id=}")

        if response2.get("success", False):
            result = response2.get("result", {})
            data_model = json.loads(result.get("model", "{}"))
            device_properties.data_model = data_model
            for service in data_model.get("services", {}):
                for property in service.get("properties", {}):
                    if (
                        "abilityId" in property
                        and "code" in property
                        and "accessMode" in property
                        and "typeSpec" in property
                    ):
                        dp_id = int(property["abilityId"])
                        code = property["code"]
                        typeSpec = property["typeSpec"]
                        real_type = TuyaDPType.try_parse(typeSpec["type"])
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

        if response.get("success", False):
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
                        real_type = TuyaDPType.try_parse(dp_type)
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
                    XTDeviceWatcherCategory.IOT_API,
                )
                result = self.api.post(
                    f"/v2.0/cloud/thing/{device_id}/shadow/properties/issue",
                    {"properties": property_str},
                )
                if result.get("success") is False:
                    raise Exception(
                        f"send_property_update error:({properties}): {result}"
                    )

    def send_lock_unlock_command(
        self,
        device: XTDevice,
        lock: bool,
        force_unlock_mechanism: XTLockingMechanism = XTLockingMechanism.AUTO,
    ) -> bool:
        self.multi_manager.device_watcher.report_message(
            device.id,
            f"Sending lock/unlock command open: {lock}",
            XTDeviceWatcherCategory.IOT_API,
        )
        return self.send_lock_unlock_command_multi_api(
            device, lock, force_unlock_mechanism
        )

    def _lock_unlock_command_door_operate(
        self,
        device: XTDevice,
        lock: bool,
        api: XTIOTOpenAPI,
        supported_unlock_types: list[str],
    ) -> bool:
        if lock:
            open = "false"
        else:
            open = "true"
        if "remoteUnlockWithoutPwd" in supported_unlock_types:
            return self.call_door_operate(device, open, api)
        return False

    def _lock_unlock_command_door_open(
        self,
        device: XTDevice,
        lock: bool,
        api: XTIOTOpenAPI,
        supported_unlock_types: list[str],
    ) -> bool:
        if "remoteUnlockWithoutPwd" in supported_unlock_types:
            if lock:
                # Locking of the door
                return False
            else:
                # Unlocking of the door
                return self.call_door_open(device, api)
        return False

    def _lock_unlock_command_dpcode_command(
        self, device: XTDevice, lock: bool, api: XTIOTOpenAPI
    ) -> bool:
        if manual_unlock_code := cast(
            list[XTDPCode],
            device.get_preference(
                XTDevice.XTDevicePreference.LOCK_MANUAL_UNLOCK_COMMAND
            ),
        ):
            commands: list[dict[str, Any]] = []
            for dpcode in manual_unlock_code:
                status_value = device.status.get(dpcode)
                if status_value is not None and not isinstance(status_value, bool):
                    # Status value can sometimes be a string, in that case we want to send that string to the cloud
                    commands.append({"code": dpcode, "value": status_value})
                else:
                    # Otherwise, we want to send the lock/unlock command as a boolean
                    commands.append({"code": dpcode, "value": not lock})
            return self.multi_manager.send_commands(
                device_id=device.id, commands=commands
            )
        return False

    def _lock_unlock_command_ticket_flow(
        self, device: XTDevice, lock: bool, api: XTIOTOpenAPI
    ) -> bool:
        # Request password ticket and run door-operate with standard boolean value
        return self.call_door_operate(device, not lock, api)

    def send_lock_unlock_command_multi_api(
        self,
        device: XTDevice,
        lock: bool,
        force_locking_mechanism: XTLockingMechanism = XTLockingMechanism.AUTO,
        api: XTIOTOpenAPI | None = None,
    ) -> bool:
        if api is None:
            if self.send_lock_unlock_command_multi_api(
                device, lock, force_locking_mechanism, self.non_user_api
            ):
                return True
            else:
                return self.send_lock_unlock_command_multi_api(
                    device, lock, force_locking_mechanism, self.api
                )

        match force_locking_mechanism:
            case XTLockingMechanism.DOOR_OPERATE:
                return self._lock_unlock_command_door_operate(
                    device, lock, api, self.get_supported_unlock_types(device, api)
                )
            case XTLockingMechanism.DOOR_OPEN:
                return self._lock_unlock_command_door_open(
                    device, lock, api, self.get_supported_unlock_types(device, api)
                )
            case XTLockingMechanism.TICKET_FLOW:
                return self._lock_unlock_command_ticket_flow(device, lock, api)
            case XTLockingMechanism.DPCODE_COMMAND:
                return self._lock_unlock_command_dpcode_command(device, lock, api)
            case _:
                # Default to AUTO behavior
                unlock_types = self.get_supported_unlock_types(device, api)
                if self._lock_unlock_command_door_operate(
                    device, lock, api, unlock_types
                ):
                    return True
                if self._lock_unlock_command_door_open(device, lock, api, unlock_types):
                    return True
                if self._lock_unlock_command_dpcode_command(device, lock, api):
                    return True
                if self._lock_unlock_command_ticket_flow(device, lock, api):
                    return True
        return False

    def test_lock_api_subscription(
        self, device: XTDevice, api: XTIOTOpenAPI | None = None
    ) -> bool:
        api_to_use = api or self.api
        ticket = api_to_use.post(f"/v1.0/devices/{device.id}/door-lock/password-ticket")
        if code := ticket.get("code", None):
            if code in TUYA_TEST_API_BAD_RETURN_CODES:
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
            if code in TUYA_TEST_API_BAD_RETURN_CODES:
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
            if code in TUYA_TEST_API_BAD_RETURN_CODES:
                return False
        return True

    def test_sensor_energy_statistic_api_subscription(
        self, device: XTDevice, api: XTIOTOpenAPI | None = None
    ) -> bool:
        if api is None:
            if self.test_sensor_energy_statistic_api_subscription(device, self.api):
                if self.test_sensor_energy_statistic_api_subscription(
                    device, self.non_user_api
                ):
                    return True
            return False
        stat_type = api.get(f"/v1.0/devices/{device.id}/all-statistic-type")
        if code := stat_type.get("code", None):
            if code in TUYA_TEST_API_BAD_RETURN_CODES:
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
            device.id,
            f"API remote unlock types: {remote_unlock_types}",
            XTDeviceWatcherCategory.IOT_API,
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
        self, device: XTDevice, api: XTIOTOpenAPI | None = None
    ) -> str | None:
        api_to_use = api or self.api
        try:
            ticket = api_to_use.post(f"/v1.0/devices/{device.id}/door-lock/password-ticket")
            self.multi_manager.device_watcher.report_message(
                device.id,
                f"API remote unlock ticket: {ticket}",
                XTDeviceWatcherCategory.IOT_API,
            )
            if ticket.get("success", False):
                result: dict[str, Any] = ticket.get("result", {})
                if ticket_id := result.get("ticket_id", None):
                    LOGGER.debug(f"[Tuya Lock Ticket] Ticket obtained for device {device.id}: {ticket_id}")
                    return ticket_id

            LOGGER.warning(
                f"[Tuya Lock Ticket] Failed to obtain password ticket for device {device.id}. Response: {ticket}"
            )
        except Exception as e:
            LOGGER.error(
                f"[Tuya Lock Ticket] Exception while obtaining password ticket for device {device.id}: {e}",
                exc_info=True,
            )
        return None

    def call_door_operate(self, device: XTDevice, open: str | bool, api: XTIOTOpenAPI) -> bool:
        ticket_id = self.get_door_lock_password_ticket(device, api)
        if not ticket_id:
            LOGGER.error(f"[Tuya Lock Operate] Cannot operate lock {device.id}: Ticket generation failed.")
            return False

        api_to_use = cast(
            XTIOTOpenAPI,
            device.get_preference(
                f"{MESSAGE_SOURCE_TUYA_IOT}{XTDevice.XTDevicePreference.LOCK_CALL_DOOR_OPERATE}",
                api,
            ),
        )
        try:
            lock_operation = api_to_use.post(
                f"/v1.0/smart-lock/devices/{device.id}/password-free/door-operate",
                {"ticket_id": ticket_id, "open": open},
            )
            self.multi_manager.device_watcher.report_message(
                device.id,
                f"API call_door_operate result: {lock_operation}",
                XTDeviceWatcherCategory.IOT_API,
            )
            if lock_operation.get("success", False):
                device.set_preference(
                    f"{MESSAGE_SOURCE_TUYA_IOT}{XTDevice.XTDevicePreference.LOCK_CALL_DOOR_OPERATE}",
                    api_to_use,
                )
                LOGGER.info(f"[Tuya Lock Operate] Successfully operated door lock {device.id} (open={open}).")
                if hasattr(self.multi_manager, "hass") and self.multi_manager.hass:
                    self.multi_manager.hass.bus.fire(
                        "xtend_tuya_lock_operated",
                        {"device_id": device.id, "open": open, "success": True, "response": lock_operation},
                    )
                return True

            LOGGER.error(
                f"[Tuya Lock Operate] Door operate failed for {device.id} (open={open}). Response: {lock_operation}"
            )
            if hasattr(self.multi_manager, "hass") and self.multi_manager.hass:
                self.multi_manager.hass.bus.fire(
                    "xtend_tuya_lock_operated",
                    {"device_id": device.id, "open": open, "success": False, "response": lock_operation},
                )
        except Exception as e:
            LOGGER.error(
                f"[Tuya Lock Operate] Exception during call_door_operate for {device.id}: {e}",
                exc_info=True,
            )
        return False

    def call_door_open(self, device: XTDevice, api: XTIOTOpenAPI) -> bool:
        ticket_id = self.get_door_lock_password_ticket(device, api)
        if not ticket_id:
            LOGGER.error(f"[Tuya Lock Open] Cannot open door {device.id}: Ticket generation failed.")
            return False

        api_to_use = cast(
            XTIOTOpenAPI,
            device.get_preference(
                f"{MESSAGE_SOURCE_TUYA_IOT}{XTDevice.XTDevicePreference.LOCK_CALL_DOOR_OPEN}",
                api,
            ),
        )
        try:
            lock_operation = api.post(
                f"/v1.0/devices/{device.id}/door-lock/password-free/open-door",
                {"ticket_id": ticket_id},
            )
            self.multi_manager.device_watcher.report_message(
                device.id,
                f"API call_door_open result: {lock_operation}",
                XTDeviceWatcherCategory.IOT_API,
            )
            if lock_operation.get("success", False):
                device.set_preference(
                    f"{MESSAGE_SOURCE_TUYA_IOT}{XTDevice.XTDevicePreference.LOCK_CALL_DOOR_OPEN}",
                    api_to_use,
                )
                LOGGER.info(f"[Tuya Lock Open] Successfully opened door lock {device.id}.")
                if hasattr(self.multi_manager, "hass") and self.multi_manager.hass:
                    self.multi_manager.hass.bus.fire(
                        "xtend_tuya_lock_opened",
                        {"device_id": device.id, "success": True, "response": lock_operation},
                    )
                return True

            LOGGER.error(
                f"[Tuya Lock Open] Door open failed for {device.id}. Response: {lock_operation}"
            )
            if hasattr(self.multi_manager, "hass") and self.multi_manager.hass:
                self.multi_manager.hass.bus.fire(
                    "xtend_tuya_lock_opened",
                    {"device_id": device.id, "success": False, "response": lock_operation},
                )
        except Exception as e:
            LOGGER.error(
                f"[Tuya Lock Open] Exception during call_door_open for {device.id}: {e}",
                exc_info=True,
            )
        return False

    def get_door_lock_password_ticket_data(
        self, device: XTDevice, api: XTIOTOpenAPI | None = None
    ) -> tuple[str | None, str | None]:
        """Obtain password ticket_id and ticket_key for a door lock."""
        api_to_use = api or self.api
        try:
            ticket = api_to_use.post(f"/v1.0/devices/{device.id}/door-lock/password-ticket")
            self.multi_manager.device_watcher.report_message(
                device.id,
                f"API remote unlock ticket: {ticket}",
                XTDeviceWatcherCategory.IOT_API,
            )
            if ticket.get("success", False):
                res_data: dict[str, Any] = ticket.get("result", {})
                t_id = res_data.get("ticket_id")
                t_key = res_data.get("ticket_key")
                return t_id, t_key
        except Exception as e:
            LOGGER.error(
                f"[Tuya Lock Ticket] Exception while obtaining password ticket data for device {device.id}: {e}",
                exc_info=True,
            )
        return None, None

    def create_temporary_password(
        self,
        device: XTDevice,
        password: str,
        name: str | None = None,
        effective_time: int | None = None,
        invalid_time: int | None = None,
        api: XTIOTOpenAPI | None = None,
    ) -> dict[str, Any]:
        """Create a temporary password for a smart lock via Tuya Cloud API."""
        apis_to_try = [api] if api else [self.api]
        apis_to_try = [a for a in apis_to_try if a is not None]

        now_ms = int(time.time() * 1000)
        eff_time = effective_time if effective_time is not None else now_ms
        inv_time = invalid_time if invalid_time is not None else now_ms + (24 * 3600 * 1000)

        res: dict[str, Any] = {}
        for api_to_use in apis_to_try:
            ticket_id, ticket_key = self.get_door_lock_password_ticket_data(device, api_to_use)
            if not ticket_id:
                ticket_id = self.get_door_lock_password_ticket(device, api_to_use)

            encrypted_pass = str(password)
            if ticket_key and hasattr(api_to_use, "access_secret") and api_to_use.access_secret:
                try:
                    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
                    from cryptography.hazmat.backends import default_backend

                    sec_bytes = api_to_use.access_secret.encode("utf-8")
                    tk_bytes = bytes.fromhex(ticket_key)
                    cipher_dec = Cipher(algorithms.AES(sec_bytes), modes.ECB(), backend=default_backend())
                    decryptor = cipher_dec.decryptor()
                    raw_dec = decryptor.update(tk_bytes) + decryptor.finalize()

                    pad_val = raw_dec[-1]
                    if 1 <= pad_val <= 16 and raw_dec.endswith(bytes([pad_val]) * pad_val):
                        key_16 = raw_dec[:-pad_val]
                    else:
                        key_16 = raw_dec[:16]

                    pin_str = str(password)
                    pad_l = 16 - (len(pin_str) % 16)
                    padded_pin = pin_str.encode("utf-8") + bytes([pad_l] * pad_l)
                    cipher_enc = Cipher(algorithms.AES(key_16), modes.ECB(), backend=default_backend())
                    encryptor = cipher_enc.encryptor()
                    enc_bytes = encryptor.update(padded_pin) + encryptor.finalize()
                    encrypted_pass = enc_bytes.hex()
                except Exception as err:
                    LOGGER.warning(f"[Tuya Temp Password] Encryption attempt failed for device {device.id}: {err}")

            payload: dict[str, Any] = {
                "password": encrypted_pass,
                "name": name or "HA Temp Password",
                "effective_time": eff_time,
                "invalid_time": inv_time,
                "password_type": "ticket",
            }
            if ticket_id:
                payload["ticket_id"] = ticket_id

            try:
                res = api_to_use.post(
                    f"/v1.0/devices/{device.id}/door-lock/temp-password",
                    payload,
                )
                self.multi_manager.device_watcher.report_message(
                    device.id,
                    f"API create_temporary_password result (/v1.0/devices/door-lock/temp-password): {res}",
                    XTDeviceWatcherCategory.IOT_API,
                )

                if res.get("success", False):
                    LOGGER.info(
                        f"[Tuya Temp Password] Successfully created temporary password '{name}' for device {device.id}. Result: {res.get('result')}"
                    )
                    break
                else:
                    LOGGER.warning(
                        f"[Tuya Temp Password] Attempt with API {api_to_use} failed for device {device.id}. Response: {res}"
                    )
            except Exception as e:
                LOGGER.error(
                    f"[Tuya Temp Password] Exception during create_temporary_password for {device.id}: {e}",
                    exc_info=True,
                )
                res = {"success": False, "error": str(e)}

        if hasattr(self.multi_manager, "hass") and self.multi_manager.hass:
            self.multi_manager.hass.bus.fire(
                "xtend_tuya_temp_password_created",
                {
                    "device_id": device.id,
                    "name": name,
                    "effective_time": eff_time,
                    "invalid_time": inv_time,
                    "success": res.get("success", False),
                    "response": res,
                },
            )

        return res

    def get_temporary_passwords(
        self,
        device: XTDevice,
        api: XTIOTOpenAPI | None = None,
    ) -> list[dict[str, Any]]:
        """Get all active temporary passwords for a Tuya smart lock."""
        apis_to_try = [api] if api else [self.api]
        apis_to_try = [a for a in apis_to_try if a is not None]

        for api_to_use in apis_to_try:
            try:
                res = api_to_use.get(f"/v1.0/devices/{device.id}/door-lock/temp-passwords")
                LOGGER.info(f"[Tuya Temp Password] GET temp-passwords response for device {device.id}: {res}")
                if res and res.get("success", False):
                    return res.get("result", [])
            except Exception as e:
                LOGGER.error(f"[Tuya Temp Password] Exception in get_temporary_passwords for {device.id}: {e}", exc_info=True)
        return []

    def delete_temporary_password(
        self,
        device: XTDevice,
        password_id: int | str,
        api: XTIOTOpenAPI | None = None,
    ) -> dict[str, Any]:
        """Delete a temporary password from a Tuya smart lock by password_id.

        If the password has already expired (code 2304), automatically falls back to
        deleting the expired password record via the /record endpoint.
        """
        apis_to_try = [api] if api else [self.api]
        apis_to_try = [a for a in apis_to_try if a is not None]

        res: dict[str, Any] = {}
        for api_to_use in apis_to_try:
            try:
                # 1. Try normal delete for active password
                res = api_to_use.delete(f"/v1.0/devices/{device.id}/door-lock/temp-passwords/{password_id}")
                LOGGER.info(f"[Tuya Temp Password] DELETE temp-passwords/{password_id} response for device {device.id}: {res}")

                # 2. If password has expired (code 2304 or message says expired), delete the expired record
                code = res.get("code") if isinstance(res, dict) else None
                msg = str(res.get("msg", "")).lower() if isinstance(res, dict) else ""
                if not res.get("success", False) and (code == 2304 or "expired" in msg):
                    LOGGER.info(f"[Tuya Temp Password] Password {password_id} is expired (code {code}). Attempting /record deletion fallback...")
                    record_res = api_to_use.delete(f"/v1.0/devices/{device.id}/door-lock/temp-passwords/{password_id}/record")
                    LOGGER.info(f"[Tuya Temp Password] DELETE temp-passwords/{password_id}/record response: {record_res}")
                    if record_res and record_res.get("success", False):
                        res = record_res
                    elif isinstance(record_res, dict) and record_res.get("code") in (2302, 2323):
                        # 2302: password does not exist, 2323: door lock password record does not exist
                        res = {"success": True, "result": True, "note": "Password record does not exist or was already removed"}
                    elif record_res:
                        res = record_res

                # 3. Idempotent success if password already doesn't exist
                if isinstance(res, dict) and not res.get("success", False) and res.get("code") in (2302, 2323):
                    res = {"success": True, "result": True, "note": "Password does not exist or was already removed"}

                if res and res.get("success", False):
                    break
            except Exception as e:
                LOGGER.error(f"[Tuya Temp Password] Exception in delete_temporary_password for {device.id}: {e}", exc_info=True)
                res = {"success": False, "error": str(e)}

        if hasattr(self.multi_manager, "hass") and self.multi_manager.hass:
            self.multi_manager.hass.bus.fire(
                "xtend_tuya_temp_password_deleted",
                {
                    "device_id": device.id,
                    "password_id": password_id,
                    "success": res.get("success", False),
                    "response": res,
                },
            )
        return res


    def get_dynamic_password(
        self,
        device: XTDevice,
        api: XTIOTOpenAPI | None = None,
    ) -> dict[str, Any] | None:
        """Get or calculate 8-digit 5-minute dynamic password for lock with 0-API local cache."""
        now_ts = int(time.time())
        current_window = now_ts // 300
        window_end = (current_window + 1) * 300

        cache_key = f"dynamic_passcode_{device.id}"
        if not hasattr(self, "_passcode_cache"):
            self._passcode_cache: dict[str, dict[str, Any]] = {}

        cached = self._passcode_cache.get(cache_key)
        if cached and cached.get("window") == current_window:
            return {
                "dynamic_password": cached["dynamic_password"],
                "valid_until": window_end,
            }

        # 1. Cloud API fetch first (cached per 5-minute window, ~1 call every 5 mins)
        api_to_use = api or self.api
        ticket_id = self.get_door_lock_password_ticket(device, api_to_use)

        endpoints = [
            f"/v1.0/devices/{device.id}/door-lock/dynamic-password",
            f"/v1.0/smart-lock/devices/{device.id}/dynamic-passwords",
            f"/v1.0/smart-lock/devices/{device.id}/dynamic-password",
            f"/v1.0/devices/{device.id}/door-lock/dynamic-passwords",
            f"/v1.0/smart-lock/devices/{device.id}/password-free/dynamic-password",
        ]
        if ticket_id:
            endpoints.insert(0, f"/v1.0/devices/{device.id}/door-lock/dynamic-password?ticket_id={ticket_id}")
            endpoints.insert(1, f"/v1.0/smart-lock/devices/{device.id}/dynamic-password?ticket_id={ticket_id}")

        errors_log = []
        for endpoint in endpoints:
            try:
                res = api_to_use.get(endpoint)
                LOGGER.info(f"[Tuya Lock Passcode] GET {endpoint} response: {res}")
                if res and res.get("success", False):
                    result = res.get("result", {})
                    passcode = None

                    if isinstance(result, (str, int)):
                        passcode = f"{int(result):08d}" if str(result).isdigit() else str(result)
                    elif isinstance(result, dict):
                        raw_code = (
                            result.get("dynamic_password")
                            or result.get("dynamicPassword")
                            or result.get("password")
                            or result.get("code")
                            or result.get("random_password")
                        )
                        if raw_code is not None:
                            passcode = f"{int(raw_code):08d}" if str(raw_code).isdigit() else str(raw_code)

                    if passcode:
                        LOGGER.info(f"[Tuya Lock Passcode] Cloud API succeeded for {device.id}: {passcode}")
                        self._passcode_cache[cache_key] = {"window": current_window, "dynamic_password": passcode}
                        return {
                            "dynamic_password": passcode,
                            "valid_until": window_end,
                        }
                else:
                    errors_log.append(f"{endpoint} -> {res}")
            except Exception as e:
                errors_log.append(f"{endpoint} exception -> {e}")

        # 2. Fallback to local calculation if Cloud API endpoints fail
        local_key = getattr(device, "local_key", "") or ""
        if not local_key and hasattr(device, "status") and isinstance(device.status, dict):
            local_key = device.status.get("local_key", "")
        if local_key:
            code = self._calculate_offline_dynamic_passcode(local_key, device.id)
            if code:
                LOGGER.warning(f"[Tuya Lock Passcode] Cloud API failed ({errors_log}), falling back to local calculation for {device.id}: {code}")
                self._passcode_cache[cache_key] = {"window": current_window, "dynamic_password": code}
                return {
                    "dynamic_password": code,
                    "valid_until": window_end,
                }

        LOGGER.error(
            f"[Tuya Lock Passcode] Failed to obtain passcode for {device.id}. "
            f"Has local_key: {bool(local_key)}. Ticket ID: {ticket_id}. Cloud API responses: {errors_log}"
        )
        return None



    @staticmethod
    def _calculate_offline_dynamic_passcode(local_key: str, device_id: str) -> str | None:
        """Calculate Tuya 8-digit 5-minute offline dynamic passcode."""
        try:
            now_ts = int(time.time())
            window = now_ts // 300
            key_bytes = local_key.encode("utf-8")
            msg_bytes = f"{device_id}_{window}".encode("utf-8")
            digest = hmac.new(key_bytes, msg_bytes, hashlib.sha256).digest()
            offset = digest[-1] & 0x0F
            code_num = (
                ((digest[offset] & 0x7F) << 24)
                | ((digest[offset + 1] & 0xFF) << 16)
                | ((digest[offset + 2] & 0xFF) << 8)
                | (digest[offset + 3] & 0xFF)
            )
            return f"{code_num % 100000000:08d}"
        except Exception:
            return None


