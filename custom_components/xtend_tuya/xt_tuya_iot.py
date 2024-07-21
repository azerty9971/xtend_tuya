"""
This file contains all the code that inherit from IOT sdk from Tuya:
https://github.com/tuya/tuya-iot-python-sdk
"""

from __future__ import annotations
import json
from tuya_iot import (
    AuthType,
    TuyaDevice,
    TuyaDeviceListener,
    TuyaDeviceManager,
    TuyaHomeManager,
    TuyaOpenAPI,
    TuyaOpenMQ,
)
from typing import Any, Optional
from homeassistant.helpers import device_registry as dr
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import (
    CONF_ENDPOINT,
    CONF_TERMINAL_ID,
    CONF_TOKEN_INFO,
    CONF_USER_CODE,
    DOMAIN,
    DOMAIN_ORIG,
    LOGGER,
    PLATFORMS,
    TUYA_CLIENT_ID,
    TUYA_DISCOVERY_NEW,
    TUYA_HA_SIGNAL_UPDATE_ENTITY,
    VirtualStates,
    DescriptionVirtualState,
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_APP_TYPE,
    CONF_AUTH_TYPE,
    CONF_COUNTRY_CODE,
    CONF_ENDPOINT_OT,
    CONF_PASSWORD,
    CONF_USERNAME,
    DPType,
)
from .multi_manager import (
    MultiManager,
    XTDeviceFunction,
    XTDeviceStatusRange,
    XTDeviceProperties,
)
from .util import (
    determine_property_type, 
    prepare_value_for_property_update,
    log_stack
)

class XTTuyaDevice(TuyaDevice):
    set_up: Optional[bool] = True
    support_local: Optional[bool] = True
    local_strategy: dict[int, dict[str, Any]] = {}
    force_open_api: Optional[bool] = False

class XTDeviceListener(TuyaDeviceListener):
    """Device Update Listener."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_manager: TuyaDeviceManager,
        device_ids: set[str],
    ) -> None:
        """Init DeviceListener."""
        self.hass = hass
        self.device_manager = device_manager
        self.device_ids = device_ids

    def update_device(self, device: TuyaDevice) -> None:
        """Update device status."""
        if device.id in self.device_ids:
            LOGGER.debug(
                "Received update for device %s: %s",
                device.id,
                self.device_manager.device_map[device.id].status,
            )
            dispatcher_send(self.hass, f"{TUYA_HA_SIGNAL_UPDATE_ENTITY}_{device.id}")

    def add_device(self, device: TuyaDevice) -> None:
        """Add device added listener."""
        # Ensure the device isn't present stale
        self.hass.add_job(self.async_remove_device, device.id)

        self.device_ids.add(device.id)
        dispatcher_send(self.hass, TUYA_DISCOVERY_NEW, [device.id])

        other_device_manager = self.device_manager.get_overriden_device_manager()
        device_manager = self.device_manager
        if other_device_manager is None:
            device_manager.mq.stop()
            tuya_mq = TuyaOpenMQ(device_manager.api)
            tuya_mq.start()

            device_manager.mq = tuya_mq
            tuya_mq.add_message_listener(device_manager.on_message)
        else:
            device_manager.mq = other_device_manager.mq

    def remove_device(self, device_id: str) -> None:
        """Add device removed listener."""
        if device_manager := self.device_manager.get_overriden_device_manager():
            device_manager.remove_device(device_id)
        self.hass.add_job(self.async_remove_device, device_id)

    @callback
    def async_remove_device(self, device_id: str) -> None:
        log_stack("XTDeviceListener => async_remove_device")
        """Remove device from Home Assistant."""
        LOGGER.debug("Remove device: %s", device_id)
        device_registry = dr.async_get(self.hass)
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, device_id)}
        )
        if device_entry is not None:
            device_registry.async_remove_device(device_entry.id)
            self.device_ids.discard(device_id)

class XTTuyaDeviceManager(TuyaDeviceManager):
    def __init__(self, multi_manager: MultiManager, api: TuyaOpenAPI, mq: TuyaOpenMQ) -> None:
        super().__init__(api, mq)
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
        #DEBUG
        """shared_dev_id = "bf85bd241924094329wbx0"
        force_open_api = True
        shared_dev = self.get_device_info(shared_dev_id)
        LOGGER.warning(f"shared_dev => {shared_dev}")
        if shared_dev["success"]:
            item = shared_dev["result"]
            device = XTTuyaDevice(**item)
            device.force_open_api = force_open_api
            status = {}
            api_status = self.get_device_status(shared_dev_id)
            if api_status["success"]:
                api_status_result = api_status["result"]
                for item_status in api_status_result:
                    if "code" in item_status and "value" in item_status:
                        code = item_status["code"]
                        value = item_status["value"]
                        status[code] = value
                device.status = status
                self.device_map[item["id"]] = device"""
            #LOGGER.warning(f"User ID: {self.api.token_info.uid}")
        #ENDDEBUG
        """Update devices status in project type SmartHome."""
        response = self.api.get(f"/v1.0/users/{self.api.token_info.uid}/devices")
        if response["success"]:
            for item in response["result"]:
                device = XTTuyaDevice(**item)
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
            self.multi_manager.apply_init_virtual_states(self.device_map[device_id])

    
    def on_message(self, msg: str):
        #LOGGER.warning(f"XTTuyaDeviceManager: mq receive-> {msg}")
        self.multi_manager.on_message(msg)
        super().on_message(msg)

    def _update_device_list_info_cache(self, devIds: list[str]):
        response = self.get_device_list_info(devIds)
        result = response.get("result", {})
        #LOGGER.warning(f"_update_device_list_info_cache => {devIds} <=> {response}")
        for item in result.get("list", []):
            device_id = item["id"]
            self.device_map[device_id] = XTTuyaDevice(**item)
    

    def get_device_specification(self, device_id: str) -> dict[str, str]:
        specs = super().get_device_specification(device_id)
        self.multi_manager.get_device_properties_open_api(self.device_map[device_id])
        if specs["success"]:
            if "result" in specs and "status" in specs["result"]:
                for status_code in self.device_map[device_id].status_range:
                    status = self.device_map[device_id].status_range[status_code]
                    status_found = False
                    for spec_status in specs["result"]["status"]:
                        if spec_status["code"] == status.code:
                            status_found = True
                            break
                    if not status_found:
                        specs["result"]["status"].append({"code": status.code, "type": status.type, "values": status.values})
        return specs
    
    def get_device_properties(self, device) -> XTDeviceProperties | None:
        device_properties = XTDeviceProperties()
        response = self.open_api.get(f"/v2.0/cloud/thing/{device.id}/shadow/properties")
        response2 = self.open_api.get(f"/v2.0/cloud/thing/{device.id}/model")
        if response2.get("success"):
            result = response2.get("result", {})
            model = json.loads(result.get("model", "{}"))
            for service in model["services"]:
                for property in service["properties"]:
                    if (    "abilityId" in property
                        and "code" in property
                        and "accessMode" in property
                        and "typeSpec" in property
                        ):
                        if property["abilityId"] not in device_properties.local_strategy:
                            if "type" in property["typeSpec"]:
                                typeSpec = property["typeSpec"]
                                real_type = determine_property_type(property["typeSpec"]["type"])
                                typeSpec.pop("type")
                                typeSpec = json.dumps(typeSpec)
                                device_properties.local_strategy[int(property["abilityId"])] = {
                                    "status_code": property["code"],
                                    "config_item": {
                                        "valueDesc": typeSpec,
                                        "valueType": real_type,
                                        "pid": device.product_id,
                                    },
                                    "property_update": True,
                                    "use_open_api": True
                                }
        if response.get("success"):
            result = response.get("result", {})
            for dp_property in result["properties"]:
                if "dp_id" in dp_property and "type" in dp_property:
                    if dp_property["dp_id"] not in device_properties.local_strategy:
                        dp_id = int(dp_property["dp_id"])
                        real_type = determine_property_type(dp_property.get("type",None), dp_property.get("value",None))
                        device_properties.local_strategy[dp_id] = {
                            "status_code": dp_property["code"],
                            "config_item": {
                                "valueDesc": dp_property.get("value",{}),
                                "valueType": real_type,
                                "pid": device.product_id,
                            },
                            "property_update": True,
                            "use_open_api": True
                        }
                if (    "code"  in dp_property 
                    and "dp_id" in dp_property 
                    and dp_property["dp_id"]  in device_properties.local_strategy
                    ):
                    code = dp_property["code"]
                    if code not in device_properties.status_range:
                        device_properties.status_range[code] = XTDeviceStatusRange()
                        device_properties.status_range[code].code   = code
                        device_properties.status_range[code].type   = device_properties.local_strategy[dp_property["dp_id"]]["config_item"]["valueType"]
                        device_properties.status_range[code].values = device_properties.local_strategy[dp_property["dp_id"]]["config_item"]["valueDesc"]
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
    
    """def get_overriden_device_manager(self) -> Manager | None:
        if self.manager is not None:
            return self.manager.other_device_manager
        return None
    
    def add_device(self, device):
        #Tuya
        if other_device_manager := self.get_overriden_device_manager():
            for listener in other_device_manager.device_listeners:
                listener.add_device(device)
        #XT Tuya
        if self.manager is not None:
            for listener in self.manager.device_listeners:
                listener.add_device(device)
        #OpenAPI
        for listener in self.device_listeners:
            listener.add_device(device)"""
    
async def tuya_iot_update_listener(hass, entry):
    """Handle options update."""
    LOGGER.debug(f"update_listener => {entry}")
    LOGGER.debug(f"update_listener => {entry.data}")