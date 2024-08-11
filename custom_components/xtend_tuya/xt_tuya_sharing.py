"""
This file contains all the code that inherit from Tuya integration
"""

from __future__ import annotations
from typing import Any

import uuid
import hashlib
import time
import json
import hmac

from homeassistant.core import HomeAssistant, callback

from tuya_sharing.manager import (
    Manager,
    PROTOCOL_DEVICE_REPORT,
    PROTOCOL_OTHER,
    BIZCODE_BIND_USER,
    BIZCODE_DELETE,
    BIZCODE_DPNAME_UPDATE,
    BIZCODE_NAME_UPDATE,
    BIZCODE_OFFLINE,
    BIZCODE_ONLINE,
)

from tuya_sharing.customerapi import (
    CustomerApi,
    CustomerTokenInfo,
    SharingTokenListener,
    _secret_generating,
    _form_to_json,
    _aes_gcm_encrypt,
    _aex_gcm_decrypt
)
from tuya_sharing.home import (
    SmartLifeHome,
)
from tuya_sharing.device import (
    CustomerDevice,
    DeviceRepository,
    DeviceStatusRange,
)

from .const import (
    CONF_TOKEN_INFO,
    LOGGER,
    DPType,
)

from .multi_manager import (
    MultiManager,
)

from .base import TuyaEntity

class XTSharingTokenListener(SharingTokenListener):
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

class XTSharingDeviceManager(Manager):
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
        self.mq.add_message_listener(self.multi_manager.on_message_from_tuya_sharing)
        self.mq.remove_message_listener(self.on_message)

    def set_overriden_device_manager(self, other_device_manager: Manager) -> None:
        self.other_device_manager = other_device_manager
    
    def get_overriden_device_manager(self) -> Manager | None:
        if self.other_device_manager is not None:
            return self.other_device_manager
        return None
    
    def _on_device_report(self, device_id: str, status: list):
        device = self.device_map.get(device_id, None)
        if not device:
            LOGGER.warning(f"_on_device_report sharing device not found : {device_id}")
            return
        status_new = self.multi_manager.convert_device_report_status_list(device_id, status)
        status_new = self.multi_manager.apply_virtual_states_to_status_list(device, status_new)
        LOGGER.warning(f"_on_device_report => {status_new}")
        super()._on_device_report(device_id, status_new)
    
    def send_commands(
            self, device_id: str, commands: list[dict[str, Any]]
    ):
        if other_manager := self.get_overriden_device_manager():
            other_manager.send_commands(device_id, commands)
            return
        super().send_commands(device_id, commands)

class XTSharingDeviceRepository(DeviceRepository):
    def __init__(self, customer_api: CustomerApi, manager: XTSharingDeviceManager, multi_manager: MultiManager):
        super().__init__(customer_api)
        self.manager = manager
        self.multi_manager = multi_manager

    def update_device_specification(self, device: CustomerDevice):
        super().update_device_specification(device)

    def _update_device_strategy_info_mod(self, device: CustomerDevice):
        device_id = device.id
        response = self.api.get(f"/v1.0/m/life/devices/{device_id}/status")
        support_local = True
        if response.get("success"):
            result = response.get("result", {})
            pid = result["productKey"]
            dp_id_map = {}
            for dp_status_relation in result["dpStatusRelationDTOS"]:
                if not dp_status_relation["supportLocal"]:
                    support_local = False
                    break
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
            device.support_local = support_local
            #if support_local:                      #CHANGED
            device.local_strategy = dp_id_map       #CHANGED

            #LOGGER.debug(
            #    f"device status strategy dev_id = {device_id} support_local = {support_local} local_strategy = {dp_id_map}")

    def update_device_strategy_info(self, device: CustomerDevice):
        #super().update_device_strategy_info(device)
        self._update_device_strategy_info_mod(device=device)
        if device.support_local:
            #Sometimes the Type provided by Tuya is ill formed,
            #replace it with the one from the local strategy
            for loc_strat in device.local_strategy.values():
                if "statusCode" not in loc_strat or "valueType" not in loc_strat:
                    continue
                code = loc_strat["statusCode"]
                value_type = loc_strat["valueType"]

                if code in device.status_range:
                    device.status_range[code].type = value_type
                if code in device.function:
                    device.function[code].type     = value_type

                if (
                    "valueDesc"  in loc_strat and
                    code not in device.status_range and
                    code not in device.function
                    ):
                    device.status_range[code] = DeviceStatusRange()
                    device.status_range[code].code   = code
                    device.status_range[code].type   = value_type
                    device.status_range[code].values = loc_strat["valueDesc"]

        #Sometimes the Type provided by Tuya is ill formed,
        #Try to reformat it into the correct one
        for status in device.status_range.values():
            try:
                DPType(status.type)
            except ValueError:
                status.type = TuyaEntity.determine_dptype(status.type)
        for func in device.function.values():
            try:
                DPType(func.type)
            except ValueError:
                func.type = TuyaEntity.determine_dptype(func.type)

        self.multi_manager.apply_init_virtual_states(device)
        self.multi_manager.allow_virtual_devices_not_set_up(device)