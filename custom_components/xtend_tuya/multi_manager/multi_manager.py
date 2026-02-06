from __future__ import annotations
import copy
import importlib
import os
import asyncio
from typing import Any, Literal, Optional, Callable
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from ..lib.tuya_iot.device import (
    PROTOCOL_DEVICE_REPORT,
    PROTOCOL_OTHER,
)
from ..const import (
    LOGGER,
    AllowedPlugins,
    XTDeviceEntityFunctions,
    XTMultiManagerProperties,
    XTMultiManagerPostSetupCallbackPriority,
    XTIRHubInformation,
    XTIRRemoteInformation,
    XTIRRemoteKeysInformation,
)
from .shared.shared_classes import (
    DeviceWatcher,
    XTConfigEntry,  # noqa: F811
    XTDeviceMap,
    XTDevice,
)
from .shared.threading import (
    XTConcurrencyManager,
    XTEventLoopProtector,
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
from ..entity_parser.entity_parser import (
    XTCustomEntityParser,
)
import custom_components.xtend_tuya.multi_manager.shared.data_entry.shared_data_entry as shared_data_entry


class MultiManager:  # noqa: F811
    def __init__(self, hass: HomeAssistant, config_entry: XTConfigEntry) -> None:
        self.config_entry = config_entry
        self.virtual_state_handler = XTVirtualStateHandler(self)
        self.virtual_function_handler = XTVirtualFunctionHandler(self)
        self.multi_mqtt_queue: MultiMQTTQueue = MultiMQTTQueue(self)
        self.multi_device_listener: MultiDeviceListener = MultiDeviceListener(
            hass, self
        )
        self.hass = hass
        self.multi_source_handler = MultiSourceHandler(self)
        self.device_watcher = DeviceWatcher(self)
        self.accounts: dict[str, XTDeviceManagerInterface] = {}
        self.master_device_map: XTDeviceMap = XTDeviceMap({})
        self.is_ready_for_messages = False
        self.pending_messages: list[tuple[str, dict]] = []
        self.devices_shared: dict[str, XTDevice] = {}
        self.debug_helper = DebugHelper(self)
        self.scene_id: list[str] = []
        self.general_properties: dict[str, Any] = {}
        self.entity_parsers: dict[str, XTCustomEntityParser] = {}
        self.post_setup_callbacks: dict[
            XTMultiManagerPostSetupCallbackPriority,
            list[tuple[Callable, tuple | None]],
        ] = {}
        for priority in XTMultiManagerPostSetupCallbackPriority:
            self.post_setup_callbacks[priority] = []
        self.loading_finalized: bool = False
        self._user_input_flows: dict[str, shared_data_entry.XTFlowDataBase] = {}

    @property
    def device_map(self):
        return self.master_device_map

    @property
    def mq(self):
        return self.multi_mqtt_queue

    def register_account(self, instance: XTDeviceManagerInterface):
        self.accounts[instance.get_type_name()] = instance

    def get_account_by_name(
        self, account_name: str | None
    ) -> XTDeviceManagerInterface | None:
        if account_name in self.accounts:
            return self.accounts[account_name]
        return None

    async def setup_entry(self) -> None:
        # Load all the plugins
        subdirs = AllowedPlugins.get_plugins_to_load()
        concurrency_manager = XTConcurrencyManager()
        for directory in subdirs:
            if os.path.isdir(
                os.path.dirname(__file__) + os.sep + "managers" + os.sep + directory
            ):
                load_path = f".managers.{directory}.init"
                try:
                    plugin = (
                        await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                            importlib.import_module,
                            name=load_path,
                            package=__package__,
                        )
                    )
                    LOGGER.debug(f"Plugin {load_path} loaded")
                    instance: XTDeviceManagerInterface = plugin.get_plugin_instance()
                    concurrency_manager.add_coroutine(
                        instance.setup_from_entry(self.hass, self.config_entry, self)
                    )
                except ModuleNotFoundError as e:
                    LOGGER.error(f"Loading module failed: {e}")
        await concurrency_manager.gather()
        for account in self.accounts.values():
            await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                account.on_post_setup
            )

    async def setup_entity_parsers(self) -> None:
        await XTCustomEntityParser.setup_entity_parsers(self.hass, self)

    def get_domain_identifiers_of_device(self, device_id: str) -> list:
        return_list: list = []
        for account in self.accounts.values():
            return_list = append_lists(
                return_list, account.get_domain_identifiers_of_device(device_id)
            )
        return return_list

    def get_platform_descriptors_to_merge(self, platform: Platform) -> list:
        return_list: list = []
        for account in self.accounts.values():
            if new_descriptors := account.get_platform_descriptors_to_merge(platform):
                return_list.append(new_descriptors)
        for entity_parser in self.entity_parsers.values():
            if new_descriptors := entity_parser.get_descriptors_to_merge(platform):
                return_list.append(new_descriptors)
        return return_list

    def get_platform_descriptors_to_exclude(self, platform: Platform) -> list:
        return_list: list = []
        for account in self.accounts.values():
            if new_descriptors := account.get_platform_descriptors_to_exclude(platform):
                return_list.append(new_descriptors)
        return return_list

    async def update_device_cache(self):
        self.is_ready_for_messages = False
        XTDeviceMap.clear_master_device_map()
        concurrency_manager = XTConcurrencyManager()

        async def update_manager_device_cache(
            manager: XTDeviceManagerInterface,
        ) -> None:
            await manager.update_device_cache()

        for manager in self.accounts.values():
            concurrency_manager.add_coroutine(
                update_manager_device_cache(manager=manager)
            )

        await concurrency_manager.gather()

        # Register all devices in the master device map
        self.update_master_device_map()

        # Now let's aggregate all of these devices into a single
        # "All functionnality" device
        self._merge_devices_from_multiple_sources()
        for device in self.device_map.values():
            # Applied twice because some parts at the end of apply_fix would change values of previous calls
            CloudFixes.apply_fixes(device, self)
            CloudFixes.apply_fixes(device, self)

            # Don't allow changes to DPCodes after the global initialization
            device.force_compatibility = True
        self._enable_multi_map_device_alignment()
        self._process_pending_messages()

    def _process_pending_messages(self):
        self.is_ready_for_messages = True
        for messages in self.pending_messages:
            self.on_message(messages[0], messages[1])
        self.pending_messages.clear()

    def update_master_device_map(self):
        for manager in self.accounts.values():
            for device_map in manager.get_available_device_maps():
                for device_id in device_map:
                    # New devices have been created in their own device maps
                    # let's convert them to XTDevice
                    device_map[device_id] = manager.convert_to_xt_device(
                        device_map[device_id], device_map.device_source_priority
                    )

                    if device_id not in self.master_device_map:
                        self.master_device_map[device_id] = device_map[device_id]

    def __get_available_device_maps(self) -> list[XTDeviceMap]:
        return_list: list[XTDeviceMap] = []
        for manager in self.accounts.values():
            for device_map in manager.get_available_device_maps():
                return_list.append(device_map)
        return return_list

    def _merge_devices_from_multiple_sources(self):
        # Merge the device function, status_range and status between managers
        for device in self.device_map.values():
            to_be_merged: list[XTDevice] = []
            devices = self.__get_devices_from_device_id(device.id)
            for current_device in devices:
                for prev_device in to_be_merged:
                    XTMergingManager.merge_devices(prev_device, current_device, self)
                to_be_merged.append(current_device)

    def _enable_multi_map_device_alignment(self):
        for device_map in self.__get_available_device_maps():
            XTDeviceMap.register_device_map(device_map)
        XTDeviceMap.register_device_map(self.device_map)
        self._align_multi_map_devices()

    def _align_multi_map_devices(self):
        # Refresh all master device variables with themselves to trigger alignment
        for device in self.device_map.values():
            for key, value in vars(device).items():
                setattr(device, key, value)

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
        if (
            code in device.status_range
            and hasattr(device.status_range[code], "dp_id")
            and device.status_range[code].dp_id != 0
        ):
            return device.status_range[code].dp_id
        for dpId in device.local_strategy:
            if device.local_strategy[dpId]["status_code"] == code:
                return dpId
            if (
                "status_code_alias" in device.local_strategy[dpId]
                and code in device.local_strategy[dpId]["status_code_alias"]
            ):
                return dpId
            elif "status_code_alias" not in device.local_strategy[dpId]:
                LOGGER.warning(
                    f"Device {device.name} ({device.id}) has no status_code_alias dict for dpId {dpId}, please contact the developer about this"
                )
        return None

    def _read_code_from_dpId(self, dpId: int, device: XTDevice) -> str | None:
        if dp_id_item := device.local_strategy.get(dpId, None):
            return dp_id_item["status_code"]
        return None

    def __get_devices_from_device_id(self, device_id: str) -> list[XTDevice]:
        return_list = []
        device_maps = self.__get_available_device_maps()
        for device_map in device_maps:
            if device_id in device_map:
                return_list.append(device_map[device_id])
        return return_list

    def _read_code_dpid_value_from_state(
        self,
        device_id: str,
        state,
        fail_if_dpid_not_found=True,
        fail_if_code_not_found=True,
    ):
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

            # For alias in state, replace provided code with the main code from the dpId
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
                pass
            return None, None, None, False
        if dpId is None and fail_if_dpid_not_found:
            if device:
                pass
            return None, None, None, False
        return code, dpId, value, True

    def convert_device_report_status_list(
        self, device_id: str, status_in: list
    ) -> list[dict[str, Any]]:
        status = copy.deepcopy(status_in)
        for item in status:
            code, dpId, value, result_ok = self._read_code_dpid_value_from_state(
                device_id, item
            )
            if result_ok:
                item["code"] = code
                item["dpId"] = dpId
                item["value"] = value
            else:
                pass
        return status

    def on_message(self, source: str, msg: dict):
        if not self.is_ready_for_messages:
            self.pending_messages.append((source, msg))
            return
        dev_id = self._get_device_id_from_message(msg)
        if not dev_id:
            return

        new_message = self._convert_message_for_all_accounts(msg)
        self.device_watcher.report_message(
            dev_id, f"on_message ({source}) => {msg} <=> {new_message}"
        )
        if status_list := self._get_status_list_from_message(msg):
            self.device_watcher.report_message(
                dev_id, f"On Message reporting ({source}): {msg}"
            )
            self.multi_source_handler.register_status_list_from_source(
                dev_id, source, status_list
            )
            # self.device_watcher.report_message(dev_id, f"on_message ({source}) status list => {status_list}")

        if source in self.accounts:
            self.accounts[source].on_message(new_message)

    def add_device_by_id(self, device_id: str):
        for account in self.accounts.values():
            account.add_device_by_id(device_id)
        self.update_master_device_map()

    def _get_device_id_from_message(self, msg: dict) -> str | None:
        protocol = msg.get("protocol", 0)
        data = msg.get("data", {})
        if dev_id := data.get("devId", None):
            return dev_id
        if protocol == PROTOCOL_OTHER:
            if bizData := data.get("bizData", None):
                if dev_id := bizData.get("devId", None):
                    return dev_id
        return None

    def _get_status_list_from_message(self, msg: dict) -> str | None:
        protocol = msg.get("protocol", 0)
        data = msg.get("data", {})
        if protocol == PROTOCOL_DEVICE_REPORT and "status" in data:
            return data["status"]
        return None

    def _convert_message_for_all_accounts(self, msg: dict) -> dict:
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

    def send_commands(self, device_id: str, commands: list[dict[str, Any]]):
        virtual_function_commands: list[dict[str, Any]] = []
        regular_commands: list[dict[str, Any]] = []
        if device := self.device_map.get(device_id, None):
            virtual_function_list = (
                self.virtual_function_handler.get_category_virtual_functions(
                    device.category
                )
            )
            for command in commands:
                command_code = command["code"]
                command_value = command["value"]
                LOGGER.debug(f"Base command : {command}")
                vf_found = False
                for virtual_function in virtual_function_list:
                    if (
                        command_code == virtual_function.key
                        or command_code in virtual_function.vf_reset_state
                    ):
                        command_dict = {
                            "code": command_code,
                            "value": command_value,
                            "virtual_function": virtual_function,
                        }
                        virtual_function_commands.append(command_dict)
                        vf_found = True
                        break
                if not vf_found:
                    regular_commands.append(command)
        else:
            return

        if virtual_function_commands:
            self.virtual_function_handler.process_virtual_function(
                device_id, virtual_function_commands
            )

        if regular_commands:
            for regular_command in regular_commands:
                last_command_result: bool = False
                for account in self.accounts.values():
                    if last_command_result := account.send_command(
                        device_id, regular_command, reverse_filters=False
                    ):
                        break

                # If the command failed, try using the other APIs
                if last_command_result is False:
                    for account in self.accounts.values():
                        if last_command_result := account.send_command(
                            device_id, regular_command, reverse_filters=True
                        ):
                            break
                
                # If it still didn't work, try sending the command aliases if they exist
                if last_command_result is False:
                    alias_command: list[dict[str, Any]] = []
                    if code := regular_command.get("code", None):
                        for alias in device.get_status_code_aliases(code):
                            alias_command.append(
                                {
                                    "code": alias,
                                    "value": regular_command["value"],
                                }
                            )
                    for command in alias_command:
                        last_command_result = False
                        for account in self.accounts.values():
                            if last_command_result := account.send_command(
                                device_id, command, reverse_filters=False
                            ):
                                break
                        for account in self.accounts.values():
                            if last_command_result := account.send_command(
                                device_id, command, reverse_filters=True
                            ):
                                break
                        if last_command_result is True:
                            break

    def get_device_stream_allocate(
        self, device_id: str, stream_type: Literal["flv", "hls", "rtmp", "rtsp"]
    ) -> Optional[str]:
        for account in self.accounts.values():
            if stream_allocate := account.get_device_stream_allocate(
                device_id, stream_type
            ):
                return stream_allocate

    def send_lock_unlock_command(self, device: XTDevice, lock: bool) -> bool:
        for account in self.accounts.values():
            if account.send_lock_unlock_command(device, lock):
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
                device.online = device.online_states[online_status]
                if (
                    device.online
                ):  # Prefer to be more On than Off if multiple state are not in accordance
                    break
            if device.online != old_online_status:
                self.multi_device_listener.update_device(device, None)

    def get_active_types(self) -> list[str]:
        return_list: list[str] = []
        for account in self.accounts.values():
            if account.is_type_initialized():
                return_list.append(account.get_type_name())
        return return_list

    def execute_device_entity_function(
        self,
        function: XTDeviceEntityFunctions,
        device: XTDevice,
        param1: Any | None = None,
        param2: Any | None = None,
    ):
        match function:
            case XTDeviceEntityFunctions.RECALCULATE_PERCENT_SCALE:
                if isinstance(param1, str) and isinstance(param2, int):
                    CloudFixes.fix_incorrect_percent_scale_forced(
                        device, param1, param2
                    )

    async def on_loading_finalized(
        self, hass: HomeAssistant, config_entry: XTConfigEntry
    ):
        for account in self.accounts.values():
            await account.on_loading_finalized(hass, config_entry, self)
        await self.process_post_setup_callback()
        self.loading_finalized = True

    def get_ir_hub_information(self, device: XTDevice) -> XTIRHubInformation | None:
        for account in self.accounts.values():
            ir_device_information = account.get_ir_hub_information(device)
            if ir_device_information is not None:
                return ir_device_information

    def get_ir_category_list(self, device: XTDevice) -> dict[int, str]:
        for account in self.accounts.values():
            if account_list := account.get_ir_category_list(device):
                return account_list
        return {}

    def get_ir_brand_list(self, device: XTDevice, category_id: int) -> dict[int, str]:
        for account in self.accounts.values():
            if account_list := account.get_ir_brand_list(device, category_id):
                return account_list
        return {}

    def create_ir_device(
        self,
        device: XTDevice,
        remote_name: str,
        category_id: int,
        brand_id: int,
        brand_name: str,
    ) -> str | None:
        for account in self.accounts.values():
            device_id = account.create_ir_device(
                device, remote_name, category_id, brand_id, brand_name
            )
            if device_id is not None:
                return device_id
        return None

    def send_ir_command(
        self,
        device: XTDevice,
        key: XTIRRemoteKeysInformation,
        remote: XTIRRemoteInformation,
        hub: XTIRHubInformation,
    ) -> bool:
        for account in self.accounts.values():
            if account.send_ir_command(device, key, remote, hub):
                return True
        return False

    def learn_ir_key(
        self,
        device: XTDevice,
        remote: XTIRRemoteInformation,
        hub: XTIRHubInformation,
        key: str,
        key_name: str,
        timeout: int | None = None,
    ) -> bool:
        for account in self.accounts.values():
            if account.learn_ir_key(device, remote, hub, key, key_name, timeout):
                return True
        return False

    def delete_ir_key(
        self,
        device: XTDevice,
        key: XTIRRemoteKeysInformation,
        remote: XTIRRemoteInformation,
        hub: XTIRHubInformation,
    ):
        for account in self.accounts.values():
            if account.delete_ir_key(device, key, remote, hub):
                return True
        return False

    def set_general_property(
        self, property_id: XTMultiManagerProperties, property_value: Any
    ):
        self.general_properties[property_id] = property_value

    def get_general_property(
        self, property_id: XTMultiManagerProperties, default: Any | None = None
    ) -> Any | None:
        return self.general_properties.get(property_id, default)

    async def process_post_setup_callback(self):
        for priority in XTMultiManagerPostSetupCallbackPriority:
            if priority not in self.post_setup_callbacks:
                continue
            for callback, *args in self.post_setup_callbacks[priority]:
                if args is None:
                    args = tuple()
                if asyncio.iscoroutinefunction(callback):
                    await callback(*args)
                else:
                    callback(*args)

    def add_post_setup_callback(
        self,
        priority: XTMultiManagerPostSetupCallbackPriority,
        callback: Callable,
        *args,
    ):
        if self.loading_finalized is False:
            self.post_setup_callbacks[priority].append((callback, *args))
        else:
            self.hass.add_job(callback, *args)

    def register_user_input_data(self, flow_data: shared_data_entry.XTFlowDataBase):
        if flow_data.flow_id is not None:
            self._user_input_flows[flow_data.flow_id] = flow_data

    def get_user_input_data(
        self, flow_id: str
    ) -> shared_data_entry.XTFlowDataBase | None:
        return self._user_input_flows.get(flow_id)
