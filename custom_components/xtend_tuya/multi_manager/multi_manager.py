from __future__ import annotations
from functools import partial
import copy
import importlib
import os
from typing import Any, Literal, Optional

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tuya_iot.device import (
    PROTOCOL_DEVICE_REPORT,
    PROTOCOL_OTHER,
)

from ..const import (
    LOGGER,
    AllowedPlugins,
    XTDeviceEntityFunctions,
    XTDeviceSourcePriority,
)

from .shared.import_stub import (
    MultiManager,
    XTConfigEntry,
    XTDevice,
)

from .shared.device import (
    XTDevice  # noqa: F811
)

from .shared.shared_classes import (
    DeviceWatcher,
    XTConfigEntry,  # noqa: F811
    XTDeviceMap,
)

from .shared.debug.debug_helper import (
    DebugHelper,
)

from .shared.merging_manager import (
    XTMergingManager,
)

from .shared.cloud_fix import (
    CloudFixes,
)

from .shared.multi_source_handler import (
    MultiSourceHandler,
)

from .shared.multi_mq import (
    MultiMQTTQueue,
)

from .shared.multi_device_listener import (
    MultiDeviceListener,
)

from .shared.multi_virtual_state_handler import (
    XTVirtualStateHandler,
)

from .shared.multi_virtual_function_handler import (
    XTVirtualFunctionHandler,
)

from ..util import (
    append_lists,
)

from .shared.interface.device_manager import (
    XTDeviceManagerInterface,
)
    
class MultiManager:  # noqa: F811
    def __init__(self, hass: HomeAssistant) -> None:
        self.virtual_state_handler = XTVirtualStateHandler(self)
        self.virtual_function_handler = XTVirtualFunctionHandler(self)
        self.multi_mqtt_queue: MultiMQTTQueue = MultiMQTTQueue(self)
        self.multi_device_listener: MultiDeviceListener = MultiDeviceListener(hass, self)
        self.hass = hass
        self.multi_source_handler = MultiSourceHandler(self)
        self.device_watcher = DeviceWatcher(self)
        self.accounts: dict[str, XTDeviceManagerInterface] = {}
        self.master_device_map: dict[str, XTDevice] = {}
        self.is_ready_for_messages = False
        self.pending_messages: list[tuple[str, str]] = []
        self.devices_shared: dict[str, XTDevice] = {}
        self.debug_helper = DebugHelper(self)
        self.scene_id: list[str] = []

    @property
    def device_map(self):
        return self.master_device_map
    
    @property
    def mq(self):
        return self.multi_mqtt_queue

    def get_account_by_name(self, account_name:str) -> XTDeviceManagerInterface | None:
        if account_name in self.accounts:
            return self.accounts[account_name]
        return None

    async def setup_entry(self, hass: HomeAssistant, config_entry: XTConfigEntry) -> None:
        #Load all the plugins
        #subdirs = await self.hass.async_add_executor_job(os.listdir, os.path.dirname(__file__))
        subdirs = AllowedPlugins.get_plugins_to_load()
        for directory in subdirs:
            if os.path.isdir(os.path.dirname(__file__) + os.sep + directory):
                load_path = f".{directory}.init"
                try:
                    plugin = await self.hass.async_add_executor_job(partial(importlib.import_module, name=load_path, package=__package__))
                    LOGGER.debug(f"Plugin {load_path} loaded")
                    instance: XTDeviceManagerInterface = plugin.get_plugin_instance()
                    if await instance.setup_from_entry(hass, config_entry, self):
                        self.accounts[instance.get_type_name()] = instance
                except ModuleNotFoundError as e:
                    LOGGER.error(f"Loading module failed: {e}")

        for account in self.accounts.values():
            await self.hass.async_add_executor_job(account.on_post_setup)
    
    def get_domain_identifiers_of_device(self, device_id: str) -> list:
        return_list: list = []
        for account in self.accounts.values():
            return_list = append_lists(return_list, account.get_domain_identifiers_of_device(device_id))
        return return_list
    
    def get_platform_descriptors_to_merge(self, platform: Platform) -> list:
        return_list: list = []
        for account in self.accounts.values():
            if new_descriptors := account.get_platform_descriptors_to_merge(platform):
                return_list.append(new_descriptors)
        return return_list
    
    def update_device_cache(self):
        self.is_ready_for_messages = False
        for key, manager in self.accounts.items():
            manager.update_device_cache()

            #New devices have been created in their own device maps
            #let's convert them to XTDevice
            for device_map in manager.get_available_device_maps():
                for device_id in device_map:
                    device_map[device_id] = manager.convert_to_xt_device(device_map[device_id], device_map.device_source_priority)
        
        #Register all devices in the master device map
        self._update_master_device_map()

        #Now let's aggregate all of these devices into a single
        #"All functionnality" device
        self._merge_devices_from_multiple_sources()
        for device in self.device_map.values():
            #Applied twice because some parts at the end of apply_fix would change values of previous calls
            CloudFixes.apply_fixes(device)
            CloudFixes.apply_fixes(device)
        self._process_pending_messages()

    def _process_pending_messages(self):
        self.is_ready_for_messages = True
        for messages in self.pending_messages:
            self.on_message(messages[0], messages[1])
        self.pending_messages.clear()

    def _update_master_device_map(self):
        for manager in self.accounts.values():
            for device_map in manager.get_available_device_maps():
                for device_id in device_map:
                    if device_id not in self.master_device_map:
                        self.master_device_map[device_id] = device_map[device_id]

    def __get_available_device_maps(self) -> list[XTDeviceMap]:
        return_list: list[XTDeviceMap] = []
        for manager in self.accounts.values():
            for device_map in manager.get_available_device_maps():
                return_list.append(device_map)
        return return_list

    def _merge_devices_from_multiple_sources(self):
        #Merge the device function, status_range and status between managers
        for device in self.device_map.values():
            to_be_merged: list[XTDevice] = []
            devices = self.__get_devices_from_device_id(device.id)
            for current_device in devices:
                for prev_device in to_be_merged:
                    XTMergingManager.merge_devices(prev_device, current_device, self)
                to_be_merged.append(current_device)
    
    def unload(self):
        for manager in self.accounts.values():
            manager.unload()
    
    def refresh_mq(self):
        for manager in self.accounts.values():
            manager.refresh_mq()

    def register_device_descriptors(self, name: str, descriptors):
        self.virtual_state_handler.register_device_descriptors(name, descriptors)
        self.virtual_function_handler.register_device_descriptors(name, descriptors)
    
    def remove_device_listeners(self) -> None:
        for manager in self.accounts.values():
            manager.remove_device_listeners()
    
    def _read_dpId_from_code(self, code: str, device: XTDevice) -> int | None:
        if not hasattr(device, "local_strategy"):
            return None
        if ( code in device.status_range 
            and hasattr(device.status_range[code], "dp_id") 
            and device.status_range[code].dp_id is not None
            ):
            return device.status_range[code].dp_id
        for dpId in device.local_strategy:
            if device.local_strategy[dpId]["status_code"] == code:
                return dpId
            if "status_code_alias" in device.local_strategy[dpId] and code in device.local_strategy[dpId]["status_code_alias"]:
                return dpId
            elif "status_code_alias" not in device.local_strategy[dpId]:
                LOGGER.warning(f"Device {device.name} ({device.id}) has no status_code_alias dict for dpId {dpId}, please contact the developer about this")
        return None
    
    def _read_code_from_dpId(self, dpId: int, device: XTDevice) -> str | None:
        if dp_id_item := device.local_strategy.get(dpId, None):
            return dp_id_item["status_code"]
        return None
    
    def __get_devices_from_device_id(self, device_id: str) -> list[XTDevice] | None:
        return_list = []
        device_maps = self.__get_available_device_maps()
        for device_map in device_maps:
            if device_id in device_map:
                return_list.append(device_map[device_id])
        return return_list

    def _read_code_dpid_value_from_state(self, device_id: str, state, fail_if_dpid_not_found = True, fail_if_code_not_found = True):
        code = None
        dpId = None
        value = None
        if "value" in state:
            value = state["value"]
        if device := self.device_map.get(device_id, None):
            if code is None and "code" in state:
                code = state["code"]
            if dpId is None and "dpId" in state:
                dpId = state["dpId"]

            if code is None and dpId is not None:
                code = self._read_code_from_dpId(dpId, device)

            if dpId is None and code is not None:
                dpId = self._read_dpId_from_code(code, device)

            #For alias in state, replace provided code with the main code from the dpId
            if dpId is not None:
                code_non_alias = self._read_code_from_dpId(dpId, device)
                if code_non_alias is not None:
                    code = code_non_alias

            if dpId is None and code is None:
                for temp_dpId in state:
                    temp_code = self._read_code_from_dpId(int(temp_dpId), device)
                    if temp_code is not None:
                        dpId = int(temp_dpId)
                        code = temp_code
                        value = state[temp_dpId]

            if code is not None and dpId is not None:
                return code, dpId, value, True
        if code is None and fail_if_code_not_found:
            if device:
                #LOGGER.warning(f"_read_code_value_from_state FAILED => {device.id} <=> {device.name} <=> {state} <=> {device.local_strategy}")
                pass
            return None, None, None, False
        if dpId is None and fail_if_dpid_not_found:
            if device:
                #LOGGER.warning(f"_read_code_value_from_state FAILED => {device.id} <=> {device.name} <=> {state} <=> {device.local_strategy}")
                pass
            return None, None, None, False
        return code, dpId, value, True

    def convert_device_report_status_list(self, device_id: str, status_in: list) -> list:
        status = copy.deepcopy(status_in)
        for item in status:
            code, dpId, value, result_ok = self._read_code_dpid_value_from_state(device_id, item)
            if result_ok:
                item["code"] = code
                item["dpId"] = dpId
                item["value"] = value
            else:
                #LOGGER.warning(f"convert_device_report_status_list code retrieval failed => {item} <=>{device_id}")
                pass
        return status

    def on_message(self, source: str, msg: str):
        if not self.is_ready_for_messages:
            self.pending_messages.append((source, msg))
            return
        dev_id = self._get_device_id_from_message(msg)
        if not dev_id:
            LOGGER.warning(f"dev_id {dev_id} not found!")
            return
        
        #self.device_watcher.report_message(dev_id, f"on_message ({source}) => {msg}")

        new_message = self._convert_message_for_all_accounts(msg)
        if status_list := self._get_status_list_from_message(msg):
            self.device_watcher.report_message(dev_id, f"On Message reporting ({source}): {msg}")
            self.multi_source_handler.register_status_list_from_source(dev_id, source, status_list)
            #self.device_watcher.report_message(dev_id, f"on_message ({source}) status list => {status_list}")
        
        if source in self.accounts:
            self.accounts[source].on_message(new_message)

    def _get_device_id_from_message(self, msg: str) -> str | None:
        protocol = msg.get("protocol", 0)
        data = msg.get("data", {})
        if (dev_id := data.get("devId", None)):
            return dev_id
        if protocol == PROTOCOL_OTHER:
            if bizData := data.get("bizData", None):
                if dev_id := bizData.get("devId", None):
                    return dev_id
        return None
    
    def _get_status_list_from_message(self, msg: str) -> str | None:
        protocol = msg.get("protocol", 0)
        data = msg.get("data", {})
        if protocol == PROTOCOL_DEVICE_REPORT and "status" in data:
            return data["status"]
        return None

    def _convert_message_for_all_accounts(self, msg: str) -> str:
        protocol = msg.get("protocol", 0)
        data = msg.get("data", {})
        if protocol == PROTOCOL_DEVICE_REPORT:
            return msg
        elif protocol == PROTOCOL_OTHER:
            if hasattr(data, "devId"):
                return msg
            else:
                if bizData := data.get("bizData", None):
                    if dev_id := bizData.get("devId", None):
                        data["devId"] = dev_id
        return msg

    def query_scenes(self) -> list:
        return_list = []
        for account in self.accounts.values():
            return_list = append_lists(return_list, account.query_scenes())
        return return_list

    def send_commands(
            self, device_id: str, commands: list[dict[str, Any]]
    ):
        virtual_function_commands: list[dict[str, Any]] = []
        regular_commands: list[dict[str, Any]] = []
        if device := self.device_map.get(device_id, None):
            virtual_function_list = self.virtual_function_handler.get_category_virtual_functions(device.category)
            for command in commands:
                command_code  = command["code"]
                command_value = command["value"]
                LOGGER.debug(f"Base command : {command}")
                vf_found = False
                for virtual_function in virtual_function_list:
                    if (
                        command_code == virtual_function.key or
                        command_code in virtual_function.vf_reset_state
                    ):
                        command_dict = {"code": command_code, "value": command_value, "virtual_function": virtual_function}
                        virtual_function_commands.append(command_dict)
                        vf_found = True
                        break
                if not vf_found:
                    regular_commands.append(command)
        
        if virtual_function_commands:
            self.virtual_function_handler.process_virtual_function(device_id, virtual_function_commands)

        if regular_commands:
            for account in self.accounts.values():
                account.send_commands(device_id, regular_commands)

    def get_device_stream_allocate(
            self, device_id: str, stream_type: Literal["flv", "hls", "rtmp", "rtsp"]
    ) -> Optional[str]:
        for account in self.accounts.values():
            if stream_allocate := account.get_device_stream_allocate(device_id, stream_type):
                return stream_allocate

    def send_lock_unlock_command(
            self, device_id: str, lock: bool
    ) -> bool:
        for account in self.accounts.values():
            if account.send_lock_unlock_command(device_id, lock):
                return True
        return False
    
    def inform_device_has_an_entity(self, device_id: str):
        for account in self.accounts.values():
            account.inform_device_has_an_entity(device_id)
    
    def trigger_scene(self, home_id: str, scene_id: str):
        for account in self.accounts.values():
            if account.trigger_scene(home_id, scene_id):
                return
    
    def update_device_online_status(self, device_id: str):
        if device := self.device_map.get(device_id, None):
            old_online_status = device.online
            for online_status in device.online_states:
                device.online = online_status
                if online_status: #Prefer to be more On than Off if multiple state are not in accordance
                    break
            if device.online != old_online_status:
                self.multi_device_listener.update_device(device, None)
    
    def get_active_types(self) -> list[str]:
        return_list: list[str] = []
        for account in self.accounts.values():
            if account.is_type_initialized():
                return_list.append(account.get_type_name())
        return return_list
    
    def execute_device_entity_function(self, function: XTDeviceEntityFunctions, device: XTDevice, param1: any | None = None):
        match function:
            case XTDeviceEntityFunctions.RECALCULATE_PERCENT_SCALE:
                CloudFixes.fix_incorrect_percent_scale_forced(device, param1)