"""
This file contains all the code that inherit from IOT sdk from Tuya:
https://github.com/tuya/tuya-iot-python-sdk
"""

from __future__ import annotations
import json
import copy
from tuya_iot import (
    TuyaDeviceManager,
    TuyaHomeManager,
    TuyaOpenAPI,
    TuyaOpenMQ,
)
from typing import Any

from ...const import (
    LOGGER,
    DPType,
)

from ..shared.shared_classes import (
    XTDeviceStatusRange,
    XTDeviceProperties,
    XTDevice,
)

from .multi_manager import (
    MultiManager,  # noqa: F811
)
from ...base import TuyaEntity

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


class XTIOTDeviceManager(TuyaDeviceManager):
    def __init__(self, multi_manager: MultiManager, api: TuyaOpenAPI, mq: TuyaOpenMQ) -> None:
        super().__init__(api, mq)
        mq.remove_message_listener(self.on_message)
        mq.add_message_listener(multi_manager.on_message_from_tuya_iot)
        self.multi_manager = multi_manager

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
                #LOGGER.warning(f"Got response => {response} <=> {result}")
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
                #result = response["result"]
                #LOGGER.warning(f"Got response => {response} <=> {result}")
                #result["online"] = result["is_online"]
                return response
            
    def update_device_list_in_smart_home(self):
        """Update devices status in project type SmartHome."""
        response  = self.api.get(f"/v1.0/users/{self.api.token_info.uid}/devices")
        response2 = self.api.get(f"/v1.0/users/{self.api.token_info.uid}/devices?from=sharing")
        if response2["success"]:
            for item in response2["result"]:
                device = XTDevice(**item)
                status = {}
                for item_status in device.status:
                    if "code" in item_status and "value" in item_status:
                        code = item_status["code"]
                        value = item_status["value"]
                        status[code] = value
                device.status = status
                self.device_map[item["id"]] = device
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
        self.update_device_function_cache()
    
    def update_device_function_cache(self, devIds: list = []):
        super().update_device_function_cache(devIds)
        for device_id in self.device_map:
            device = self.device_map[device_id]
            device_properties = self.get_device_properties(device)
            device_properties.merge_in_device(device)
            self.multi_manager.apply_init_virtual_states(device)
            self.multi_manager.allow_virtual_devices_not_set_up(device)


    
    def on_message(self, msg: str):
        super().on_message(msg)
    
    def _on_device_other(self, device_id: str, biz_code: str, data: dict[str, Any]):
        return super()._on_device_other(device_id, biz_code, data)

    def _on_device_report(self, device_id: str, status: list):
        device = self.device_map.get(device_id, None)
        if not device:
            return
        status_new = self.multi_manager.convert_device_report_status_list(device_id, status)
        status_new = self.multi_manager.apply_virtual_states_to_status_list(device, status_new)
        """devices = self.multi_manager.get_devices_from_device_id(device_id)
        for current_device in devices:
            for cur_status_new in status_new:
                current_device.status[cur_status_new["code"]] = cur_status_new["value"]"""
        super()._on_device_report(device_id, status_new)

    def _update_device_list_info_cache(self, devIds: list[str]):
        response = self.get_device_list_info(devIds)
        result = response.get("result", {})
        #LOGGER.warning(f"_update_device_list_info_cache => {devIds} <=> {response}")
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
            return
        
        if response2.get("success"):
            result = response2.get("result", {})
            model = json.loads(result.get("model", "{}"))
            device_properties.model = model
            for service in model["services"]:
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
                                "use_open_api": True
                            }
                        #Sometimes the default returned typeSpec from the regular Tuya Properties is wrong
                        #override it with the QueryThingsDataModel one
                        if real_type == DPType.ENUM: #Enums should not be altered since sometimes the model is wrong about them
                            continue
                        devices = self.multi_manager.get_devices_from_device_id(device.id)
                        for cur_device in devices:
                            if dp_id in cur_device.local_strategy:
                                cur_device.local_strategy[dp_id]["config_item"]["valueDesc"] = typeSpec_json
                                if code in cur_device.status_range:
                                    cur_device.status_range[code].values = typeSpec_json
                                if code in cur_device.function:
                                    cur_device.function[code].values = typeSpec_json


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
                            "use_open_api": True
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
                #LOGGER.warning(f"send_property_update => {property_str}")
                self.api.post(f"/v2.0/cloud/thing/{device_id}/shadow/properties/issue", {"properties": property_str}
        )