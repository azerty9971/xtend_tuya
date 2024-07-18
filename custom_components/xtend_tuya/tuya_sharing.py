"""
This file contains all the code that inherit from Tuya integration
"""

from __future__ import annotations
from typing import Any
import json
import copy

from homeassistant.helpers import device_registry as dr
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.config_entries import ConfigEntry

from tuya_sharing.manager import (
    Manager,
    SharingDeviceListener,
)
from tuya_sharing.customerapi import (
    CustomerTokenInfo,
    CustomerApi,
    SharingTokenListener,
)
from tuya_sharing.home import (
    SmartLifeHome,
    HomeRepository,
)
from tuya_sharing.device import (
    CustomerDevice,
    DeviceRepository,
    DeviceFunction,
    DeviceStatusRange,
)
from tuya_sharing.scenes import (
    SceneRepository,
)
from tuya_sharing.user import (
    UserRepository,
)
from tuya_sharing.mq import SharingMQ
from tuya_sharing.strategy import strategy
from tuya_sharing.manager import (
    PROTOCOL_DEVICE_REPORT,
    PROTOCOL_OTHER,
)

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
from .. import XTConfigEntry
from .util import (
    determine_property_type, 
    prepare_value_for_property_update,
    log_stack
)
from .sensor import (
    SENSORS,
)

class DeviceListener(SharingDeviceListener):
    """Device Update Listener."""

    def __init__(
        self,
        hass: HomeAssistant,
        manager: Manager,
    ) -> None:
        """Init DeviceListener."""
        self.hass = hass
        self.manager = manager

    def update_device(self, device: CustomerDevice) -> None:
        """Update device status."""
        #LOGGER.debug(
        #    "Received update for device %s: %s",
        #    device.id,
        #    self.manager.device_map[device.id].status,
        #)
        dispatcher_send(self.hass, f"{TUYA_HA_SIGNAL_UPDATE_ENTITY}_{device.id}")

    def add_device(self, device: CustomerDevice) -> None:
        """Add device added listener."""
        # Ensure the device isn't present stale
        self.hass.add_job(self.async_remove_device, device.id)

        dispatcher_send(self.hass, TUYA_DISCOVERY_NEW, [device.id])

    def remove_device(self, device_id: str) -> None:
        """Add device removed listener."""
        self.hass.add_job(self.async_remove_device, device_id)

    @callback
    def async_remove_device(self, device_id: str) -> None:
        """Remove device from Home Assistant."""
        log_stack("DeviceListener => async_remove_device")
        device_registry = dr.async_get(self.hass)
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, device_id)}
        )
        if device_entry is not None:
            device_registry.async_remove_device(device_entry.id)


class TokenListener(SharingTokenListener):
    """Token listener for upstream token updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: XTConfigEntry,
    ) -> None:
        """Init TokenListener."""
        self.hass = hass
        self.entry = entry

    def update_token(self, token_info: dict[str, Any]) -> None:
        """Update token info in config entry."""
        data = {
            **self.entry.data,
            CONF_TOKEN_INFO: {
                "t": token_info["t"],
                "uid": token_info["uid"],
                "expire_time": token_info["expire_time"],
                "access_token": token_info["access_token"],
                "refresh_token": token_info["refresh_token"],
            },
        }

        @callback
        def async_update_entry() -> None:
            """Update config entry."""
            self.hass.config_entries.async_update_entry(self.entry, data=data)

        self.hass.add_job(async_update_entry)

class DeviceManager(Manager):
    def __init__(
        self,
        other_device_manager: Manager = None
    ) -> None:
        self.terminal_id = None
        self.mq = None
        self.customer_api = None
        self.home_repository = None
        self.device_repository = None
        self.scene_repository = None
        self.user_repository = None
        self.device_map: dict[str, CustomerDevice] = {}
        self.user_homes: list[SmartLifeHome] = []
        self.device_listeners = set()
        self.other_device_manager = other_device_manager
    
    def refresh_mq(self):
        log_stack("refresh_mq")
        if self.other_device_manager is not None:
            self.other_device_manager.refresh_mq()
            self.mq = self.other_device_manager.mq
            self.mq.add_message_listener(self.on_message)
            self.mq.remove_message_listener(self.other_device_manager.on_message)
            return
        super().refresh_mq()
    
    def send_commands(
            self, device_id: str, commands: list[dict[str, Any]]
    ):
        open_api_regular_commands = []
        regular_commands = []
        property_commands = []
        if device_id in self.device_map:
            device = self.device_map.get(device_id, None)
            if device is not None:
                for command in commands:
                    for dp_id in device.local_strategy:
                        dp_item = device.local_strategy[dp_id]
                        code = dp_item.get("status_code", None)
                        value = command["value"]
                        if command["code"] == code:
                            if dp_item.get("use_open_api", True):
                                command_dict = {"code": code, "value": value}
                                regular_commands.append(command_dict)
                            else:
                                if dp_item.get("property_update", False):
                                    value = prepare_value_for_property_update(dp_item, command["value"])
                                    property_dict = {str(code): value}
                                    property_commands.append(property_dict)
                                else:
                                    command_dict = {"code": code, "value": value}
                                    open_api_regular_commands.append(command_dict)
                                break
                if regular_commands:
                    self.device_repository.send_commands(device_id, regular_commands)
                if open_api_regular_commands:
                    self.open_api_device_manager.send_commands(device_id, open_api_regular_commands)
                if property_commands:
                    self.open_api_device_manager.send_property_update(device_id, property_commands)
                return
        self.device_repository.send_commands(device_id, commands)

    def get_device_properties_open_api(self, device):
        device_id = device.id
        if self.open_api is None:
            return
        
        tuya_device = None
        tuya_manager = self.get_overriden_device_manager()
        if tuya_manager is None:
            tuya_manager = self
        if device.id in tuya_manager.device_map:
            tuya_device = tuya_manager.device_map[device.id]

        response = self.open_api.get(f"/v2.0/cloud/thing/{device_id}/shadow/properties")
        response2 = self.open_api.get(f"/v2.0/cloud/thing/{device_id}/model")
        if response.get("success") and response2.get("success"):
            result = response2.get("result", {})
            model = json.loads(result.get("model", "{}"))
            for service in model["services"]:
                for property in service["properties"]:
                    if (    "abilityId" in property
                        and "code" in property
                        and "accessMode" in property
                        and "typeSpec" in property
                        ):
                        if property["abilityId"] not in device.local_strategy:
                            if "type" in property["typeSpec"]:
                                typeSpec = property["typeSpec"]
                                real_type = determine_property_type(property["typeSpec"]["type"])
                                typeSpec.pop("type")
                                typeSpec = json.dumps(typeSpec)
                                device.local_strategy[property["abilityId"]] = {
                                    "status_code": property["code"],
                                    "config_item": {
                                        "valueDesc": typeSpec,
                                        "valueType": real_type,
                                        "pid": device.product_id,
                                    },
                                    "property_update": True,
                                    "use_open_api": True
                                }
                                if tuya_device is not None:
                                    device.local_strategy[property["abilityId"]] = {
                                        "status_code": property["code"],
                                        "config_item": {
                                            "valueDesc": typeSpec,
                                            "valueType": real_type,
                                            "pid": device.product_id,
                                        },
                                        "property_update": True,
                                        "use_open_api": True
                                        
                                    }

        result = response.get("result", {})
        for dp_property in result["properties"]:
            if "dp_id" in dp_property and "type" in dp_property:
                if dp_property["dp_id"] not in device.local_strategy:
                    dp_id = dp_property["dp_id"]
                    real_type = determine_property_type(dp_property.get("type",None), dp_property.get("value",None))
                    device.local_strategy[dp_id] = {
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
                and dp_property["dp_id"]  in device.local_strategy
                ):
                code = dp_property["code"]
                if code not in device.status_range:
                    device.status_range[code] = DeviceStatusRange()
                    device.status_range[code].code   = code
                    device.status_range[code].type   = device.local_strategy[dp_property["dp_id"]]["config_item"]["valueType"]
                    device.status_range[code].values = device.local_strategy[dp_property["dp_id"]]["config_item"]["valueDesc"]
                if code not in device.status:
                    device.status[code] = dp_property.get("value",None)
                #Also add the status range for Tuya's manager devices
                if tuya_device is not None and code not in tuya_device.status_range:
                    tuya_device.status_range[code] = DeviceStatusRange()
                    tuya_device.status_range[code].code   = code
                    tuya_device.status_range[code].type   = device.local_strategy[dp_property["dp_id"]]["config_item"]["valueType"]
                    tuya_device.status_range[code].values = device.local_strategy[dp_property["dp_id"]]["config_item"]["valueDesc"]
                if tuya_device is not None and code not in tuya_device.status:
                    tuya_device.status[code] = dp_property.get("value",None)

    def update_device_cache(self):
        super().update_device_cache()

        #Add Tuya OpenAPI devices to the cache
        if self.open_api_home_manager is not None:
            self.open_api_home_manager.update_device_cache()
            self.open_api_device_map = {}
            if self.open_api_device_manager is not None:
                for device_id in self.open_api_device_manager.device_map:
                    if device_id not in self.device_map:
                        LOGGER.warning(f"Adding device {device_id} to device map")
                        self.open_api_device_ids.add(device_id)
                        self.open_api_device_map[device_id] = self.open_api_device_manager.device_map[device_id]
                        self.device_map[device_id] = self.open_api_device_manager.device_map[device_id]
                        if other_manager := self.get_overriden_device_manager():
                            other_manager.device_map[device_id] = self.open_api_device_manager.device_map[device_id]
            #LOGGER.warning(f"self.open_api_device_map => {self.open_api_device_map}")

    @staticmethod
    def get_category_virtual_states(category: str) -> list[DescriptionVirtualState]:
        to_return = []
        for virtual_state in VirtualStates:
            if (descriptions := SENSORS.get(category)):
                for description in descriptions:
                    if description.virtualstate is not None and description.virtualstate & virtual_state.value:
                        # This VirtualState is applied to this key, let's return it
                        found_virtual_state = DescriptionVirtualState(description.key, virtual_state.name, virtual_state.value, description.vs_copy_to_state)
                        to_return.append(found_virtual_state)
        return to_return
    
    def apply_init_virtual_states(self, device):
        #LOGGER.warning(f"apply_init_virtual_states BEFORE => {device.status} <=> {device.status_range}")
        virtual_states = DeviceManager.get_category_virtual_states(device.category)
        for virtual_state in virtual_states:
            if virtual_state.virtual_state_value == VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME:
                if virtual_state.key in device.status:
                    if virtual_state.key in device.status_range:
                        for new_code in virtual_state.vs_copy_to_state:
                            device.status[str(new_code)] = copy.deepcopy(device.status[virtual_state.key])
                            device.status_range[str(new_code)] = copy.deepcopy(device.status_range[virtual_state.key])
                            device.status_range[str(new_code)].code = str(new_code)
                    if virtual_state.key in device.function:
                        for new_code in virtual_state.vs_copy_to_state:
                            device.status[str(new_code)] = copy.deepcopy(device.status[virtual_state.key])
                            device.function[str(new_code)] = copy.deepcopy(device.function[virtual_state.key])
                            device.function[str(new_code)].code = str(new_code)
        #LOGGER.warning(f"apply_init_virtual_states AFTER => {device.status} <=> {device.status_range}")

    def set_overriden_device_manager(self, other_device_manager: Manager) -> None:
        self.other_device_manager = other_device_manager
    
    def get_overriden_device_manager(self) -> Manager | None:
        if self.other_device_manager is not None:
            return self.other_device_manager
        return None

    def on_message(self, msg: str):
        #If we override another device manager, first call its on_message method
        if self.other_device_manager is not None:
            self.other_device_manager.on_message(msg)
        #super().on_message(msg)
        #try:
            protocol = msg.get("protocol", 0)
            data = msg.get("data", {})

            if protocol == PROTOCOL_DEVICE_REPORT:
                self._on_device_report(data["devId"], data["status"])
            if protocol == PROTOCOL_OTHER:
                self._on_device_other(data["bizData"]["devId"], data["bizCode"], data)
        #except Exception as e:
        #    LOGGER.error(f"on message error = {e} msg => {msg}")

    def _on_device_other(self, device_id: str, biz_code: str, data: dict[str, Any]):
        #LOGGER.warning(f"mq _on_device_other-> {device_id} biz_code-> {biz_code} data-> {data}")
        super()._on_device_other(device_id, biz_code, data)

    def _read_code_value_from_state(self, device, state):
        if "code" in state and "value" in state:
            return state["code"], state["value"]
        elif "dpId" in state and "value" in state:
            dp_id_item = device.local_strategy[state["dpId"]]
            code = dp_id_item["status_code"]
            value = state["value"]
            return code, value
        return None, None

    def _on_device_report(self, device_id: str, status: list):
        device = self.device_map.get(device_id, None)
        LOGGER.debug(f"mq _on_device_report-> {device_id} status-> {status}")
        if not device:
            return
        #LOGGER.debug(f"Device found!")
        virtual_states = DeviceManager.get_category_virtual_states(device.category)
        #show_debug = False
        
        #LOGGER.debug(f"Found virtualstates -> {virtual_states}")
        for virtual_state in virtual_states:
            if virtual_state.virtual_state_value == VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME:
                for item in status:
                    code, value = self._read_code_value_from_state(device, item)
                    if code is not None and code == virtual_state.key:
                        for state_name in virtual_state.vs_copy_to_state:
                            new_status = {"code": str(state_name), "value": value}
                            status.append(new_status)
                    if code is None:
                        for dict_key in item:
                            dp_id = int(dict_key)
                            dp_id_item = device.local_strategy.get(dp_id, None)
                            if dp_id_item is not None and dp_id_item["status_code"] == virtual_state.key:
                                for state_name in virtual_state.vs_copy_to_state:
                                    new_status = {"code": str(state_name), "value": item[dict_key]}
                                    status.append(new_status)
                            break
            
            if virtual_state.virtual_state_value == VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD:
                if virtual_state.key not in device.status or device.status[virtual_state.key] is None:
                    device.status[virtual_state.key] = 0
                if virtual_state.key in device.status:
                    for item in status:
                        code, value = self._read_code_value_from_state(device, item)
                        if code == virtual_state.key:
                            item["value"] += device.status[virtual_state.key]
                            continue
                        if code is None:
                            for dict_key in item:
                                dp_id = int(dict_key)
                                dp_id_item = device.local_strategy.get(dp_id, None)
                                if dp_id_item is not None and dp_id_item["status_code"] == virtual_state.key:
                                    item[dict_key] += device.status[virtual_state.key]
                                    break
                        
        for item in status:
            code, value = self._read_code_value_from_state(device, item)
            if code is not None:
                device.status[code] = value
                continue
            for dict_key in item:
                dp_id = int(dict_key)
                dp_id_item = device.local_strategy.get(dp_id, None)
                if dp_id_item is not None:
                    code = dp_id_item["status_code"]
                    value = item[dict_key]
                    device.status[code] = value
        if self.other_device_manager is not None:
            device_other = self.other_device_manager.device_map.get(device_id, None)
            if device_other is not None:
                for item in status:
                    code, value = self._read_code_value_from_state(device, item)
                    if code is not None:
                        device_other.status[code] = value
                        continue
                    for dict_key in item:
                        dp_id = int(dict_key)
                        dp_id_item = device_other.local_strategy.get(dp_id, None)
                        if dp_id_item is not None:
                            code = dp_id_item["status_code"]
                            value = item[dict_key]
                            device_other.status[code] = value
        #if show_debug == True:
        LOGGER.debug(f"AFTER device_id -> {device_id} device_status-> {device.status} status-> {status}")
        super()._on_device_report(device_id, [])
    
    def allow_virtual_devices_not_set_up(self, device):
        if not device.id.startswith("vdevo"):
            return
        if not getattr(device, "set_up", True):
            setattr(device, "set_up", True)
        if device.id in self.other_device_manager.device_map:
            tuya_device = self.other_device_manager.device_map[device.id]
            if not getattr(tuya_device, "set_up", True):
                setattr(tuya_device, "set_up", True)

class XTDeviceRepository(DeviceRepository):
    def __init__(self, customer_api: CustomerApi, manager: DeviceManager):
        super().__init__(customer_api)
        self.manager = manager

    """def query_devices_by_home(self, home_id: str) -> list[CustomerDevice]:
        #LOGGER.warning(f"query_devices_by_home => {home_id}")
        return super().query_devices_by_home(home_id)

    def query_devices_by_ids(self, ids: list) -> list[CustomerDevice]:
        #LOGGER.warning(f"query_devices_by_home => {ids}")
        return super().query_devices_by_ids(ids)"""

    """def update_device_specification(self, device: CustomerDevice):
        device_id = device.id
        response = self.api.get(f"/v1.1/m/life/{device_id}/specifications")
        #LOGGER.warning(f"update_device_specification => {response}")
        if response.get("success"):
            result = response.get("result", {})
            function_map = {}
            for function in result["functions"]:
                code = function["code"]
                function_map[code] = DeviceFunction(**function)

            status_range = {}
            for status in result["status"]:
                code = status["code"]
                status_range[code] = DeviceStatusRange(**status)

            device.function = function_map
            device.status_range = status_range"""

    def update_device_strategy_info(self, device: CustomerDevice):
        device_id = device.id
        response = self.api.get(f"/v1.0/m/life/devices/{device_id}/status")
        #LOGGER.warning(f"update_device_strategy_info => {response}")
        support_local = True
        if response.get("success"):
            result = response.get("result", {})
            pid = result["productKey"]
            dp_id_map = {}
            tuya_device = None
            tuya_manager = self.manager.get_overriden_device_manager()
            if tuya_manager is None:
                tuya_manager = self.manager
            if device.id in tuya_manager.device_map:
                tuya_device = tuya_manager.device_map[device.id]
            for dp_status_relation in result["dpStatusRelationDTOS"]:
                if not dp_status_relation["supportLocal"]:
                    support_local = False
                else:
                # statusFormat valueDesc、valueType,enumMappingMap,pid
                    dp_id_map[dp_status_relation["dpId"]] = {
                        "value_convert": dp_status_relation["valueConvert"],
                        "status_code": dp_status_relation["statusCode"],
                        "config_item": {
                            "statusFormat": dp_status_relation["statusFormat"],
                            "valueDesc": dp_status_relation["valueDesc"],
                            "valueType": dp_status_relation["valueType"],
                            "enumMappingMap": dp_status_relation["enumMappingMap"],
                            "pid": pid,
                        }
                    }
                if "statusCode" in dp_status_relation:
                    code = dp_status_relation["statusCode"]
                    if code not in device.status_range:
                        device.status_range[code] = DeviceStatusRange()
                        device.status_range[code].code   = code
                        device.status_range[code].type   = dp_status_relation["valueType"]
                        device.status_range[code].values = dp_status_relation["valueDesc"]
                    #Also add the status range for Tuya's manager devices
                    if tuya_device is not None and code not in tuya_device.status_range:
                        tuya_device.status_range[code] = DeviceStatusRange()
                        tuya_device.status_range[code].code   = code
                        tuya_device.status_range[code].type   = dp_status_relation["valueType"]
                        tuya_device.status_range[code].values = dp_status_relation["valueDesc"]
            device.support_local = support_local
            #if support_local:
            device.local_strategy = dp_id_map
            self.manager.get_device_properties_open_api(device)
            self.manager.apply_init_virtual_states(device)
            self.manager.allow_virtual_devices_not_set_up(device)
            if tuya_device is not None:
                self.manager.apply_init_virtual_states(tuya_device)