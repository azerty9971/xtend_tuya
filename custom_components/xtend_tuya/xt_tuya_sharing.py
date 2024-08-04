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
    TUYA_DISCOVERY_NEW_ORIG,
    TUYA_HA_SIGNAL_UPDATE_ENTITY,
    TUYA_HA_SIGNAL_UPDATE_ENTITY_ORIG,
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

from .util import (
    determine_property_type, 
    prepare_value_for_property_update,
    log_stack,
)

from .multi_manager import (
    MultiManager,
)

class TokenListener(SharingTokenListener):
    """Token listener for upstream token updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry, #: XTConfigEntry,
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
        multi_manager: MultiManager,
        other_device_manager: Manager = None
    ) -> None:
        self.multi_manager = multi_manager
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
    


    def on_external_refresh_mq(self):
        if self.other_device_manager is not None:
            self.mq = self.other_device_manager.mq
            self.mq.add_message_listener(self.multi_manager.on_message_from_tuya_sharing)
            self.mq.remove_message_listener(self.other_device_manager.on_message)

    def refresh_mq(self):
        if self.other_device_manager is not None:
            if self.mq and self.mq != self.other_device_manager.mq:
                self.mq.stop()
            self.other_device_manager.refresh_mq()
            return
        super().refresh_mq()

    def set_overriden_device_manager(self, other_device_manager: Manager) -> None:
        self.other_device_manager = other_device_manager
    
    def get_overriden_device_manager(self) -> Manager | None:
        if self.other_device_manager is not None:
            return self.other_device_manager
        return None

    def update_device_cache(self):
        super().update_device_cache()
        self.multi_manager.convert_tuya_devices_to_xt(self)

    def on_message(self, msg: str):
        super().on_message(msg)

    def _on_device_other(self, device_id: str, biz_code: str, data: dict[str, Any]):
        if self.other_device_manager:
            self.other_device_manager._on_device_other(device_id, biz_code, data)
        super()._on_device_other(device_id, biz_code, data)

    def _on_device_report(self, device_id: str, status: list):
        device = self.device_map.get(device_id, None)
        if not device:
            LOGGER.warning(f"_on_device_report sharing device not found : {device_id}")
            return
        status_new = self.multi_manager.convert_device_report_status_list(device_id, status)
        status_new = self.multi_manager.apply_virtual_states_to_status_list(device, status_new)
        """devices = self.multi_manager.get_devices_from_device_id(device_id)
        for current_device in devices:
            for status in status_new:
                current_device.status[status["code"]] = status["value"]"""
        super()._on_device_report(device_id, status_new)
    
    def send_commands(
            self, device_id: str, commands: list[dict[str, Any]]
    ):
        if other_manager := self.get_overriden_device_manager():
            other_manager.send_commands(device_id, commands)
            return
        super().send_commands(device_id, commands)

class XTDeviceRepository(DeviceRepository):
    def __init__(self, customer_api: CustomerApi, manager: DeviceManager, multi_manager: MultiManager):
        super().__init__(customer_api)
        self.manager = manager
        self.multi_manager = multi_manager

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
            self.multi_manager.apply_init_virtual_states(device)
            self.multi_manager.allow_virtual_devices_not_set_up(device)
            if tuya_device is not None:
                self.multi_manager.apply_init_virtual_states(tuya_device)