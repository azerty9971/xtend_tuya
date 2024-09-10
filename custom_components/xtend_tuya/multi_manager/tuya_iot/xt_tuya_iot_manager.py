"""
This file contains all the code that inherit from IOT sdk from Tuya:
https://github.com/tuya/tuya-iot-python-sdk
"""

from __future__ import annotations
import json
import copy
from tuya_iot import (
    TuyaDeviceManager,
    TuyaOpenAPI,
    TuyaOpenMQ,
)
from typing import Any

from ...const import (
    LOGGER,
    MESSAGE_SOURCE_TUYA_IOT,
)

from ..shared.device import (
    XTDevice,
)

from ..shared.shared_classes import (
    XTDeviceStatusRange,
    XTDeviceProperties,
)

from ..multi_manager import (
    MultiManager,  # noqa: F811
)
from ...base import TuyaEntity
from .xt_tuya_iot_mq import (
    XTIOTOpenMQIPC,
)
from .xt_tuya_iot_ipc_listener import (
    XTIOTIPCListener,
)


class XTIOTDeviceManager(TuyaDeviceManager):
    def __init__(self, multi_manager: MultiManager, api: TuyaOpenAPI, mq: TuyaOpenMQ) -> None:
        super().__init__(api, mq)
        mq.remove_message_listener(self.on_message)
        mq.add_message_listener(self.forward_message_to_multi_manager)
        self.multi_manager = multi_manager
        self.ipc_mq: XTIOTOpenMQIPC = XTIOTOpenMQIPC(api)
        self.ipc_listener: XTIOTIPCListener = XTIOTIPCListener(self.multi_manager)
        self.ipc_mq.start()
        self.ipc_mq.add_message_listener(self.ipc_listener.forward_message_to_multi_manager)

    def forward_message_to_multi_manager(self, msg:str):
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

    #Copy of the Tuya original method with some minor modifications
    def update_device_list_in_smart_home_mod(self):
        response = self.api.get(f"/v1.0/users/{self.api.token_info.uid}/devices")
        if response["success"]:
            for item in response["result"]:
                device = XTDevice(**item)       #CHANGED
                status = {}
                for item_status in device.status:
                    if "code" in item_status and "value" in item_status:
                        code = item_status["code"]
                        value = item_status["value"]
                        status[code] = value
                device.status = status
                self.device_map[item["id"]] = device

        #ADDED
        self.update_device_list_in_smart_home_from_sharing()
        #END ADDED

        self.update_device_function_cache()

    def update_device_list_in_smart_home_from_sharing(self):
        response = self.api.get(f"/v1.0/users/{self.api.token_info.uid}/devices?from=sharing")
        if response["success"]:
            for item in response["result"]:
                device = XTDevice(**item)
                status = {}
                for item_status in device.status:
                    if "code" in item_status and "value" in item_status:
                        code = item_status["code"]
                        value = item_status["value"]
                        status[code] = value
                device.status = status
                self.device_map[item["id"]] = device

    def update_device_list_in_smart_home(self):
        self.update_device_list_in_smart_home_mod()
    
    def update_device_function_cache(self, devIds: list = []):
        super().update_device_function_cache(devIds)
        for device_id in self.device_map:
            device = self.device_map[device_id]
            device_properties = self.get_device_properties(device)
            device_properties.merge_in_device(device)
            self.multi_manager.virtual_state_handler.apply_init_virtual_states(device)

    def on_message(self, msg: str):
        super().on_message(msg)
    
    def _on_device_other(self, device_id: str, biz_code: str, data: dict[str, Any]):
        return super()._on_device_other(device_id, biz_code, data)

    def _on_device_report(self, device_id: str, status: list):
        device = self.device_map.get(device_id, None)
        if not device:
            return
        status_new = self.multi_manager.convert_device_report_status_list(device_id, status)
        status_new = self.multi_manager.multi_source_handler.filter_status_list(device_id, MESSAGE_SOURCE_TUYA_IOT, status_new)
        status_new = self.multi_manager.virtual_state_handler.apply_virtual_states_to_status_list(device, status_new)
        super()._on_device_report(device_id, status_new)

    def _update_device_list_info_cache(self, devIds: list[str]):
        response = self.get_device_list_info(devIds)
        result = response.get("result", {})
        for item in result.get("list", []):
            device_id = item["id"]
            self.device_map[device_id] = XTDevice(**item)
    
    def get_device_properties(self, device: XTDevice) -> XTDeviceProperties | None:
        device_properties = XTDeviceProperties()
        device_properties.function = copy.deepcopy(device.function)
        device_properties.status_range = copy.deepcopy(device.status_range)
        device_properties.status = copy.deepcopy(device.status)
        if (hasattr(device, "local_strategy")):
            device_properties.local_strategy = copy.deepcopy(device.local_strategy)
        response = self.api.get(f"/v2.0/cloud/thing/{device.id}/shadow/properties")
        response2 = self.api.get(f"/v2.0/cloud/thing/{device.id}/model")
        if not response.get("success") or not response2.get("success"):
            LOGGER.warning(f"Response1: {response}")
            LOGGER.warning(f"Response1: {response2}")
            return
        
        if response2.get("success"):
            result = response2.get("result", {})
            data_model = json.loads(result.get("model", "{}"))
            device_properties.data_model = data_model
            for service in data_model["services"]:
                for property in service["properties"]:
                    if (    "abilityId" in property
                        and "code" in property
                        and "accessMode" in property
                        and "typeSpec" in property
                        ):
                        dp_id = int(property["abilityId"])
                        code  = property["code"]
                        typeSpec = property["typeSpec"]
                        real_type = TuyaEntity.determine_dptype(typeSpec["type"])
                        typeSpec.pop("type")
                        typeSpec_json = json.dumps(typeSpec)
                        if dp_id not in device_properties.local_strategy:
                            if code in device_properties.function or code in device_properties.status_range:
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
                                "status_code_alias": []
                            }

        if response.get("success"):
            result = response.get("result", {})
            for dp_property in result["properties"]:
                if "dp_id" not in dp_property:
                    continue
                dp_id = int(dp_property["dp_id"])
                if "dp_id" in dp_property and "type" in dp_property:
                    code = dp_property["code"]
                    dp_type = dp_property.get("type",None)
                    if dp_id not in device_properties.local_strategy:
                        if code in device_properties.function or code in device_properties.status_range:
                            property_update = False
                        else:
                            property_update = True
                        real_type = TuyaEntity.determine_dptype(dp_type)
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
                            "status_code_alias": []
                        }
                if (    "code"  in dp_property 
                    and "dp_id" in dp_property 
                    and dp_id in device_properties.local_strategy
                    ):
                    code = dp_property["code"]
                    if code not in device_properties.status_range and code not in device_properties.function :
                        device_properties.status_range[code] = XTDeviceStatusRange(code=code, 
                                                                                   type=device_properties.local_strategy[dp_id]["config_item"]["valueType"],
                                                                                   values=device_properties.local_strategy[dp_id]["config_item"]["valueDesc"])
                    if code not in device_properties.status:
                        device_properties.status[code] = dp_property.get("value",None)
        return device_properties

    def send_property_update(
            self, device_id: str, properties: list[dict[str, Any]]
    ):
        for property in properties:
            for prop_key in property:
                property_str = f"{{\"{prop_key}\":{property[prop_key]}}}"
                self.api.post(f"/v2.0/cloud/thing/{device_id}/shadow/properties/issue", {"properties": property_str}
        )
    
    def send_lock_unlock_command(
            self, device_id: str, lock: bool
    ) -> bool:
        supported_unlock_types: list[str] = []
        if lock:
            open = "false"
        else:
            open = "true"

        remote_unlock_types = self.api.get(f"/v1.0/devices/{device_id}/door-lock/remote-unlocks")
        if remote_unlock_types.get("success", False):
            results = remote_unlock_types.get("result", [])
            for result in results:
                if result.get("open", False):
                    if supported_unlock_type := result.get("remote_unlock_type", None):
                        supported_unlock_types.append(supported_unlock_type)
        if "remoteUnlockWithoutPwd" in supported_unlock_types:
            ticket = self.api.post(f"/v1.0/devices/{device_id}/door-lock/password-ticket")
            if ticket.get("success", False):
                result = ticket.get("result", {})
                if ticket_id := result.get("ticket_id", None):
                    lock_operation = self.api.post(f"/v1.0/smart-lock/devices/{device_id}/password-free/door-operate", {"ticket_id": ticket_id, "open": open})
                    return lock_operation.get("success", False)
        return False
    
    def get_sdp_answer(self, device_id: str, sdp_offer: str) -> str | None:
        LOGGER.warning(f"get_sdp_answer for {device_id}")
        if webrtc_config := self._get_webrtc_config(device_id):
            auth_token = webrtc_config.get("auth")
            moto_id =  webrtc_config.get("moto_id")
            for topic in self.ipc_mq.mq_config.sink_topic.values():
                topic = topic.replace("{device_id}", device_id)
                topic = topic.replace("{moto_id}", moto_id)
                LOGGER.warning(f"Computed topic: {topic}")
                subscribe_result = self.mq.client.subscribe(topic)
                LOGGER.warning(f"Susbscribe result: {subscribe_result}")

            
            if not auth_token or not moto_id:
                return None
            
        return None

    def _publish_to_ipc_mqtt(self, topic: str, msg: str):
        self.ipc_mq.client.publish(topic=topic, payload=msg)

    def _get_webrtc_config(self, device_id: str):
        webrtc_config = self.api.get(f"/v1.0/devices/{device_id}/webrtc-configs")
        LOGGER.warning(f"webrtc_config: {webrtc_config}")
        if webrtc_config.get("success"):
            return webrtc_config.get("result")
        return None