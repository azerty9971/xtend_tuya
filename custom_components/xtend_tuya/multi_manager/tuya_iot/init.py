from __future__ import annotations

import requests
import json
from typing import Optional, Literal, Any, overload

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tuya_iot import (
    AuthType,
)

from .xt_tuya_iot_openapi import (
    XTIOTOpenAPI,
)

from .xt_tuya_iot_manager import (
    XTIOTDeviceManager,
)
from ..shared.interface.device_manager import (
    XTDeviceManagerInterface,
    IssueSeverity,
)
from ..shared.shared_classes import (
    XTConfigEntry,
    XTDeviceMap,
)
from ..shared.device import (
    XTDevice,
)

from .const import (
    CONF_NO_OPENAPI,
    CONF_ACCESS_ID,
    CONF_AUTH_TYPE,
    CONF_ENDPOINT_OT,
    CONF_ACCESS_SECRET,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_COUNTRY_CODE,
    CONF_APP_TYPE,
)
from .util import (
    prepare_value_for_property_update,
)

from .xt_tuya_iot_data import (
    TuyaIOTData,
)
from .xt_tuya_iot_mq import (
    XTIOTOpenMQ,
)
from .xt_tuya_iot_home_manager import (
    XTIOTHomeManager,
)
from ..multi_manager import (
    MultiManager,
)
from ...const import (
    DOMAIN,
    MESSAGE_SOURCE_TUYA_IOT,
    LOGGER,
    TUYA_DISCOVERY_NEW,
    TUYA_HA_SIGNAL_UPDATE_ENTITY,
    XTDeviceSourcePriority,
)

def get_plugin_instance() -> XTTuyaIOTDeviceManagerInterface | None:
    return XTTuyaIOTDeviceManagerInterface()

class XTTuyaIOTDeviceManagerInterface(XTDeviceManagerInterface):
    def __init__(self) -> None:
        super().__init__()
        self.iot_account: TuyaIOTData = None
        self.hass: HomeAssistant = None

    def get_type_name(self) -> str:
        return MESSAGE_SOURCE_TUYA_IOT
    
    def is_type_initialized(self) -> bool:
        return self.iot_account is not None

    async def setup_from_entry(self, hass: HomeAssistant, config_entry: XTConfigEntry, multi_manager: MultiManager) -> bool:
        self.multi_manager: MultiManager = multi_manager
        self.hass = hass
        self.iot_account: TuyaIOTData = await self._init_from_entry(hass, config_entry)
        if self.iot_account:
            return True
        return False
    
    async def _init_from_entry(self, hass: HomeAssistant, config_entry: XTConfigEntry) -> TuyaIOTData | None:
        if (
            config_entry.options is None
            or CONF_AUTH_TYPE     not in config_entry.options
            or CONF_ENDPOINT_OT   not in config_entry.options
            or CONF_ACCESS_ID     not in config_entry.options
            or CONF_ACCESS_SECRET not in config_entry.options
            or CONF_USERNAME      not in config_entry.options
            or CONF_PASSWORD      not in config_entry.options
            or CONF_COUNTRY_CODE  not in config_entry.options
            or CONF_APP_TYPE      not in config_entry.options
            ):
            if CONF_NO_OPENAPI in config_entry.options and config_entry.options[CONF_NO_OPENAPI] is True:
                return None
            await self.raise_issue(
                hass=hass, 
                config_entry=config_entry, 
                is_fixable=True, 
                severity=IssueSeverity.WARNING, 
                translation_key="tuya_iot_not_configured", 
                translation_placeholders={
                    "name": DOMAIN,
                    "config_entry_id": config_entry.title or "Config entry not found"
                },
                learn_more_url="https://github.com/azerty9971/xtend_tuya/blob/main/docs/cloud_credentials.md")
            return None
        auth_type = AuthType(config_entry.options[CONF_AUTH_TYPE])
        api = XTIOTOpenAPI(
            endpoint=config_entry.options[CONF_ENDPOINT_OT],
            access_id=config_entry.options[CONF_ACCESS_ID],
            access_secret=config_entry.options[CONF_ACCESS_SECRET],
            auth_type=auth_type,
        )
        api.set_dev_channel("hass")
        try:
            if auth_type == AuthType.CUSTOM:
                response = await hass.async_add_executor_job(
                    api.connect, config_entry.options[CONF_USERNAME], config_entry.options[CONF_PASSWORD]
                )
            else:
                response = await hass.async_add_executor_job(
                    api.connect,
                    config_entry.options[CONF_USERNAME],
                    config_entry.options[CONF_PASSWORD],
                    config_entry.options[CONF_COUNTRY_CODE],
                    config_entry.options[CONF_APP_TYPE],
                )
        except requests.exceptions.RequestException as err:
            #raise ConfigEntryNotReady(err) from err
            await self.raise_issue(
                hass=hass, 
                config_entry=config_entry, 
                is_fixable=True, 
                severity=IssueSeverity.ERROR, 
                translation_key="tuya_iot_failed_request", 
                translation_placeholders={
                    "name": DOMAIN,
                    "config_entry_id": config_entry.title or "Config entry not found"
                })
            return None

        if response.get("success", False) is False:
            #raise ConfigEntryNotReady(response)
            await self.raise_issue(
                hass=hass, 
                config_entry=config_entry, 
                is_fixable=True, 
                severity=IssueSeverity.ERROR, 
                translation_key="tuya_iot_failed_login", 
                translation_placeholders={
                    "name": DOMAIN,
                    "config_entry_id": config_entry.title or "Config entry not found"
                },
                learn_more_url="https://github.com/azerty9971/xtend_tuya/blob/main/docs/renew_cloud_credentials.md")
            return None
        mq = XTIOTOpenMQ(api)
        mq.start()
        device_manager = XTIOTDeviceManager(self.multi_manager, api, mq)
        device_ids: list[str] = list()
        home_manager = XTIOTHomeManager(api, mq, device_manager, self.multi_manager)
        device_manager.add_device_listener(self.multi_manager.multi_device_listener)
        return TuyaIOTData(
            device_manager=device_manager,
            mq=mq,
            device_ids=device_ids,
            home_manager=home_manager)

    def update_device_cache(self):
        self.iot_account.home_manager.update_device_cache()
        new_device_ids: list[str] = [device_id for device_id in self.iot_account.device_manager.device_map]
        self.iot_account.device_ids.clear()
        self.iot_account.device_ids.extend(new_device_ids)
    
    def get_available_device_maps(self) -> list[XTDeviceMap]:
        return [XTDeviceMap(self.iot_account.device_manager.device_map, XTDeviceSourcePriority.TUYA_IOT)]
    
    def refresh_mq(self):
        pass
    
    def remove_device_listeners(self) -> None:
        self.iot_account.device_manager.remove_device_listener(self.multi_manager.multi_device_listener)
    
    def unload(self):
        pass
    
    def on_message(self, msg: str):
        self.iot_account.device_manager.on_message(msg)
    
    def query_scenes(self) -> list:
        #return self.iot_account.home_manager.query_scenes()
        #Scenes should be handled by tuya_sharing
        return []
    
    def get_device_stream_allocate(
            self, device_id: str, stream_type: Literal["flv", "hls", "rtmp", "rtsp"]
    ) -> Optional[str]:
        if device_id in self.iot_account.device_ids:
            return self.iot_account.device_manager.get_device_stream_allocate(device_id, stream_type)
    
    def get_device_registry_identifiers(self) -> list:
        return [DOMAIN]
    
    def get_domain_identifiers_of_device(self, device_id: str) -> list:
        return [DOMAIN]

    def on_update_device(self, device: XTDevice) -> list[str] | None:
        if device.id in self.iot_account.device_ids:
            return [TUYA_HA_SIGNAL_UPDATE_ENTITY]
        return None
    
    def on_add_device(self, device: XTDevice) -> list[str] | None:
        if device.id in self.iot_account.device_ids:
            return [TUYA_DISCOVERY_NEW]
        return None
    
    def on_mqtt_stop(self):
        if self.iot_account.device_manager.mq:
            self.iot_account.device_manager.mq.stop()
    
    def on_post_setup(self):
        #Store the shared devices in the multi_manager's shared device list
        shared_devices = self.iot_account.device_manager.get_devices_from_sharing()
        for device in shared_devices.values():
            if device.id not in self.multi_manager.devices_shared:
                self.multi_manager.devices_shared[device.id] = device
    
    def get_platform_descriptors_to_merge(self, platform: Platform) -> Any:
        pass
    
    def send_commands(self, device_id: str, commands: list[dict[str, Any]]):
        open_api_regular_commands: list[dict[str, Any]] = []
        property_commands: list[dict[str, Any]] = []
        devices = self.get_devices_from_device_id(device_id)
        for command in commands:
            command_code  = command["code"]
            command_value = command["value"]

            #Filter commands that don't require the use of OpenAPI
            skip_command = False
            prop_command = False
            regular_command = False
            for device in devices:
                if dpId := self.multi_manager._read_dpId_from_code(command_code, device):
                    if not device.local_strategy[dpId].get("use_open_api", False):
                        skip_command = True
                        break
                    if device.local_strategy[dpId].get("property_update", False):
                        prop_command = True
                    else:
                        regular_command = True
                else:
                    skip_command = True
            if not skip_command:
                if regular_command:
                    command_dict = {"code": command_code, "value": command_value}
                    open_api_regular_commands.append(command_dict)
                elif prop_command:
                    command_value = prepare_value_for_property_update(device.local_strategy[dpId], command_value)
                    property_dict = {str(command_code): command_value}
                    property_commands.append(property_dict)
        
        if open_api_regular_commands:
            LOGGER.debug(f"Sending Open API regular command : {open_api_regular_commands}")
            self.iot_account.device_manager.send_commands(device_id, open_api_regular_commands)
        if property_commands:
            LOGGER.debug(f"Sending property command : {property_commands}")
            self.iot_account.device_manager.send_property_update(device_id, property_commands)

    @overload
    def convert_to_xt_device(self, device: Any, device_source_priority: XTDeviceSourcePriority | None = None) -> XTDevice: ...
    
    def convert_to_xt_device(self, device: XTDevice, device_source_priority: XTDeviceSourcePriority | None = None) -> XTDevice:
        #Nothing to do, tuya_iot initializes XTDevice by default...
        device.device_source_priority = device_source_priority
        return device
    
    def send_lock_unlock_command(
            self, device_id: str, lock: bool
    ) -> bool:
        return self.iot_account.device_manager.send_lock_unlock_command(device_id, lock)
    
    def call_api(self, method: str, url: str, payload: str) -> str | None:
        params: dict[str, any] = None
        if payload:
            params = json.loads(payload)
        match method:
            case "GET":
                return self.iot_account.device_manager.api.get(url, params)
            case "POST":
                return self.iot_account.device_manager.api.post(url, params)
        return None
    
    def get_webrtc_sdp_answer(self, device_id: str, session_id: str, sdp_offer: str, channel: str) -> str | None:
        return self.iot_account.device_manager.ipc_manager.webrtc_manager.get_sdp_answer(device_id, session_id, sdp_offer, channel)
    
    def get_webrtc_ice_servers(self, device_id: str, session_id: str, format: str) -> str | None:
        return self.iot_account.device_manager.ipc_manager.webrtc_manager.get_ice_servers(device_id, session_id, format)
    
    def get_webrtc_exchange_debug(self, session_id: str) -> str | None:
        session = self.iot_account.device_manager.ipc_manager.webrtc_manager.get_webrtc_session(session_id)
        if session is not None:
            return f"{session}"
        return None
    
    def delete_webrtc_session(self, device_id: str, session_id: str) -> str | None:
        return self.iot_account.device_manager.ipc_manager.webrtc_manager.delete_webrtc_session(device_id, session_id)
    
    def send_webrtc_trickle_ice(self, device_id: str, session_id: str, candidate: str) -> str | None:
        return self.iot_account.device_manager.ipc_manager.webrtc_manager.send_webrtc_trickle_ice(device_id, session_id, candidate)