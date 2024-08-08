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
        super()._on_device_report(device_id, status_new)
    
    def send_commands(
            self, device_id: str, commands: list[dict[str, Any]]
    ):
        if other_manager := self.get_overriden_device_manager():
            other_manager.send_commands(device_id, commands)
            return
        super().send_commands(device_id, commands)

class XTSharingCustomerApi(CustomerApi):
    def __init__(self, *args):
        if len(args) == 1:
            #From a CustomerAPI
            other_api: CustomerApi = args[0]
            self.session = other_api.session
            self.token_info = other_api.token_info
            self.client_id = other_api.client_id
            self.user_code = other_api.user_code
            self.endpoint = other_api.endpoint
            self.refresh_token = other_api.refresh_token
            self.token_listener = other_api.token_listener
        elif len(args) == 5:
            super().__init__(args[0], args[1], args[2], args[3], args[4])

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            return super().get(path, params)
        except Exception:
            return self._get2(path, params)
    
    def _get2(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        #try:
        return self.__request("GET", path, params, None)
        #except Exception:
        #    return None

    def __request(
            self,
            method: str,
            path: str,
            params: dict[str, Any] | None = None,
            body: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:

        self.refresh_access_token_if_need()

        access_token = self.token_info.access_token if self.token_info else ""
        sign, t = self._calculate_sign(method, path, params, body)
        headers = {
            "client_id": self.clie,
            "sign": sign,
            "sign_method": "HMAC-SHA256",
            "access_token": access_token,
            "t": str(t),
            "lang": self.lang,
        }

        LOGGER.debug(
            f"Request: method = {method}, \
                url = {self.endpoint + path},\
                params = {params},\
                body = {body},\
                t = {int(time.time()*1000)}"
        )

        response = self.session.request(
            method, self.endpoint + path, params=params, json=body, headers=headers
        )

        if response.ok is False:
            LOGGER.error(
                f"Response error: code={response.status_code}, body={response.body}"
            )
            return None

        result = response.json()

        LOGGER.warning(
            f"Response: {json.dumps(result, ensure_ascii=False, indent=2)}"
        )
        return result
    
    def _calculate_sign(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> tuple[str, int]:

        # HTTPMethod
        str_to_sign = method
        str_to_sign += "\n"

        # Content-SHA256
        content_to_sha256 = (
            "" if body is None or len(body.keys()) == 0 else json.dumps(body)
        )

        str_to_sign += (
            hashlib.sha256(content_to_sha256.encode("utf8")).hexdigest().lower()
        )
        str_to_sign += "\n"

        # Header
        str_to_sign += "\n"

        # URL
        str_to_sign += path

        if params is not None and len(params.keys()) > 0:
            str_to_sign += "?"

            params_keys = sorted(params.keys())
            query_builder = "".join(f"{key}={params[key]}&" for key in params_keys)
            str_to_sign += query_builder[:-1]

        # Sign
        t = int(time.time() * 1000)

        message = self.client_id
        if self.token_info is not None:
            message += self.token_info.access_token
        message += str(t) + str_to_sign
        sign = (
            hmac.new(
                self.token_info.refresh_token.encode("utf8"),
                msg=message.encode("utf8"),
                digestmod=hashlib.sha256,
            )
            .hexdigest()
            .upper()
        )
        return sign, t

class XTSharingDeviceRepository(DeviceRepository):
    def __init__(self, customer_api: CustomerApi, manager: XTSharingDeviceManager, multi_manager: MultiManager):
        super().__init__(XTSharingCustomerApi(customer_api))
        self.manager = manager
        self.multi_manager = multi_manager

    def update_device_specification(self, device: CustomerDevice):
        super().update_device_specification(device)

    def update_device_strategy_info(self, device: CustomerDevice):
        super().update_device_strategy_info(device)
        response2 = self.api.get(f"/v2.0/cloud/thing/{device.id}/model")
        LOGGER.warning(response2)
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