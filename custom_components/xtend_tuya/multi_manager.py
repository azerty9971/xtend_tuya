from __future__ import annotations
import requests
import copy
from typing import NamedTuple, Optional, Any
from dataclasses import dataclass, field

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady
from homeassistant.config_entries import ConfigEntry
import homeassistant.components.tuya as tuya_integration

from tuya_iot import (
    AuthType,
    TuyaDevice,
    TuyaDeviceListener,
    TuyaDeviceManager,
    TuyaHomeManager,
    TuyaOpenAPI,
    TuyaOpenMQ,
)
from tuya_iot.device import (
    PROTOCOL_DEVICE_REPORT,
    PROTOCOL_OTHER,
)

from tuya_sharing import (
    Manager as TuyaSharingManager,
    CustomerDevice
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
from tuya_sharing.scenes import (
    SceneRepository,
)
from tuya_sharing.user import (
    UserRepository,
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
    MESSAGE_SOURCE_TUYA_IOT,
    MESSAGE_SOURCE_TUYA_SHARING,
)

from .shared_classes import (
    XTDeviceProperties,
    XTDevice,
)

from .import_stub import (
    MultiManager,
    XTConfigEntry,
)

from .util import (
    get_overriden_tuya_integration_runtime_data,
    get_tuya_integration_runtime_data,
    prepare_value_for_property_update
)

from .tuya_decorators import (
    decorate_tuya_manager,
    decorate_tuya_integration,
)

from .xt_tuya_sharing import (
    DeviceManager,
    TokenListener,
    DeviceListener,
    XTDeviceRepository,
)
from .xt_tuya_iot import (
    XTTuyaDeviceManager,
    XTDeviceListener,
    tuya_iot_update_listener,
)

type XTConfigEntry = ConfigEntry[HomeAssistantXTData]  # noqa: F811

class HomeAssistantXTData(NamedTuple):
    """Tuya data stored in the Home Assistant data object."""

    multi_manager: MultiManager
    reuse_config: bool = False

    @property
    def manager(self) -> MultiManager:
        return self.multi_manager

class TuyaIOTData(NamedTuple):
    device_manager: XTTuyaDeviceManager
    mq: TuyaOpenMQ
    device_ids: list[str] #List of device IDs that are managed by the manager before the managers device merging process
    device_listener: XTDeviceListener
    home_manager: TuyaHomeManager

class TuyaSharingData(NamedTuple):
    device_manager: DeviceManager
    device_ids: list[str] #List of device IDs that are managed by the manager before the managers device merging process

class MultiMQTTQueue:
    def __init__(self, multi_manager: MultiManager) -> None:
        self.multi_manager = multi_manager
        self.sharing_account_mq = None
        self.iot_account_mq = None

    def stop(self) -> None:
        if self.sharing_account_mq and not self.multi_manager.reuse_config:
            self.sharing_account_mq.stop()
        if self.iot_account_mq:
            self.iot_account_mq.stop()

class MultiDeviceListener:
     def __init__(self, multi_manager: MultiManager) -> None:
        self.multi_manager = multi_manager
        self.sharing_account_device_listener = None
        self.iot_account_device_listener = None
    
class MultiManager:  # noqa: F811
    def __init__(self, entry: XTConfigEntry) -> None:
        self.sharing_account: TuyaSharingData = None
        self.iot_account: TuyaIOTData = None
        self.reuse_config: bool = False
        self.descriptors = {}
        self.multi_mqtt_queue: MultiMQTTQueue = MultiMQTTQueue(self)
        self.multi_device_listener: MultiDeviceListener = MultiDeviceListener(self)
        self.config_entry = entry

    @property
    def device_map(self):
        return self.get_aggregated_device_map()
    
    @property
    def mq(self):
        return self.multi_mqtt_queue

    async def setup_entry(self, hass: HomeAssistant) -> None:
        if (account := await self.get_iot_account(hass, self.config_entry)):
            self.iot_account = account
        if (account := await self.get_sharing_account(hass,self.config_entry)):
            self.sharing_account = account

    async def overriden_tuya_entry_updated(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        LOGGER.warning("overriden_tuya_entry_updated")

    async def get_sharing_account(self, hass: HomeAssistant, entry: XTConfigEntry) -> TuyaSharingData | None:
        #See if our current entry is an override of a Tuya integration entry
        tuya_integration_runtime_data = get_overriden_tuya_integration_runtime_data(hass, entry)
        if tuya_integration_runtime_data:
            #We are using an override of the Tuya integration
            decorate_tuya_manager(tuya_integration_runtime_data.device_manager, self)
            decorate_tuya_integration(self)
            sharing_device_manager = DeviceManager(multi_manager=self, other_device_manager=tuya_integration_runtime_data.device_manager)
            sharing_device_manager.terminal_id      = tuya_integration_runtime_data.device_manager.terminal_id
            sharing_device_manager.mq               = tuya_integration_runtime_data.device_manager.mq
            sharing_device_manager.customer_api     = tuya_integration_runtime_data.device_manager.customer_api
            sharing_device_manager.device_listeners = tuya_integration_runtime_data.device_manager.device_listeners
            self.reuse_config = True
        else:
            #We are using XT as a standalone integration
            sharing_device_manager = DeviceManager(multi_manager=self, other_device_manager=None)
            token_listener = TokenListener(hass, entry)
            sharing_device_manager.terminal_id = entry.data[CONF_TERMINAL_ID]
            sharing_device_manager.customer_api = CustomerApi(
                CustomerTokenInfo(entry.data[CONF_TOKEN_INFO]),
                TUYA_CLIENT_ID,
                entry.data[CONF_USER_CODE],
                entry.data[CONF_ENDPOINT],
                token_listener,
            )
            sharing_device_manager.mq = None
        self.multi_mqtt_queue.sharing_account_mq = sharing_device_manager.mq
        sharing_device_manager.home_repository = HomeRepository(sharing_device_manager.customer_api)
        sharing_device_manager.device_repository = XTDeviceRepository(sharing_device_manager.customer_api, sharing_device_manager, self)
        sharing_device_manager.scene_repository = SceneRepository(sharing_device_manager.customer_api)
        sharing_device_manager.user_repository = UserRepository(sharing_device_manager.customer_api)
        self.multi_device_listener.sharing_account_device_listener = DeviceListener(hass, sharing_device_manager)
        sharing_device_manager.add_device_listener(self.multi_device_listener.sharing_account_device_listener)
        return TuyaSharingData(device_manager=sharing_device_manager, device_ids=[])

    async def get_iot_account(self, hass: HomeAssistant, entry: XTConfigEntry) -> TuyaIOTData | None:
        if (
            entry.options is None
            or CONF_AUTH_TYPE     not in entry.options
            or CONF_ENDPOINT_OT   not in entry.options
            or CONF_ACCESS_ID     not in entry.options
            or CONF_ACCESS_SECRET not in entry.options
            or CONF_USERNAME      not in entry.options
            or CONF_PASSWORD      not in entry.options
            or CONF_COUNTRY_CODE  not in entry.options
            or CONF_APP_TYPE      not in entry.options
            ):
            return None
        auth_type = AuthType(entry.options[CONF_AUTH_TYPE])
        api = TuyaOpenAPI(
            endpoint=entry.options[CONF_ENDPOINT_OT],
            access_id=entry.options[CONF_ACCESS_ID],
            access_secret=entry.options[CONF_ACCESS_SECRET],
            auth_type=auth_type,
        )
        api.set_dev_channel("hass")
        try:
            if auth_type == AuthType.CUSTOM:
                response = await hass.async_add_executor_job(
                    api.connect, entry.options[CONF_USERNAME], entry.options[CONF_PASSWORD]
                )
            else:
                response = await hass.async_add_executor_job(
                    api.connect,
                    entry.options[CONF_USERNAME],
                    entry.options[CONF_PASSWORD],
                    entry.options[CONF_COUNTRY_CODE],
                    entry.options[CONF_APP_TYPE],
                )
        except requests.exceptions.RequestException as err:
            raise ConfigEntryNotReady(err) from err

        if response.get("success", False) is False:
            raise ConfigEntryNotReady(response)
        entry.async_on_unload(entry.add_update_listener(tuya_iot_update_listener))
        mq = TuyaOpenMQ(api)
        self.multi_mqtt_queue.iot_account_mq = mq
        mq.start()
        device_manager = XTTuyaDeviceManager(self, api, mq)
        device_ids: list[str] = list()
        self.multi_device_listener.iot_account_device_listener = XTDeviceListener(hass, device_manager, device_ids, self)
        home_manager = TuyaHomeManager(api, mq, device_manager)
        device_manager.add_device_listener(self.multi_device_listener.iot_account_device_listener)
        return TuyaIOTData(
            device_manager=device_manager,
            mq=mq,
            device_ids=device_ids,
            device_listener=self.multi_device_listener.iot_account_device_listener, 
            home_manager=home_manager)
    
    def update_device_cache(self):
        if self.sharing_account:
            self.sharing_account.device_manager.update_device_cache()
            self.sharing_account.device_ids.clear()
            new_device_ids: list[str] = [device_id for device_id in self.sharing_account.device_manager.device_map]
            self.sharing_account.device_ids.extend(new_device_ids)
        if self.iot_account:
            self.iot_account.home_manager.update_device_cache()
            self.iot_account.device_ids.clear()
            new_device_ids: list[str] = [device_id for device_id in self.iot_account.device_manager.device_map]
            self.iot_account.device_ids.extend(new_device_ids)
        self._merge_devices_from_multiple_sources()
    
    def _get_available_device_maps(self) -> list[dict[str, XTDevice]]:
        return_list: list[dict[str, XTDevice]] = list()
        if self.sharing_account:
            if other_manager := self.sharing_account.device_manager.get_overriden_device_manager():
                return_list.append(other_manager.device_map)
            return_list.append(self.sharing_account.device_manager.device_map)
        if self.iot_account:
            return_list.append(self.iot_account.device_manager.device_map)
        return return_list

    def _merge_devices_from_multiple_sources(self):
        if not ( self.sharing_account and self.iot_account ):
            return
        
        #Merge the device function, status_range and status between managers
        device_maps = self._get_available_device_maps()
        aggregated_device_list = self.get_aggregated_device_map()
        for device in aggregated_device_list.values():
            to_be_merged = []
            for device_map in device_maps:
                if device.id in device_map:
                    current_device = device_map[device.id]
                    for prev_device in to_be_merged:
                        self._merge_devices(current_device, prev_device)
                        self._merge_devices(prev_device, current_device)
                    to_be_merged.append(current_device)
        for device_map in device_maps:
            device_map.update(aggregated_device_list)
        
    def _merge_devices(self, receiving_device: XTDevice, giving_device: XTDevice):
        receiving_device.status_range.update(giving_device.status_range)
        receiving_device.function.update(giving_device.function)
        receiving_device.status.update(giving_device.status)
        #giving_device.status = receiving_device.status
        if hasattr(receiving_device, "local_strategy") and hasattr(giving_device, "local_strategy"):
            receiving_device.local_strategy.update(giving_device.local_strategy)

    def is_device_in_domain_device_maps(self, domains: list[str], device_entry_identifiers: list[str]):
        if device_entry_identifiers[0] in domains:
            if self.sharing_account and device_entry_identifiers[1] in self.sharing_account.device_manager.device_map:
                return True
            if self.iot_account and device_entry_identifiers[1] in self.iot_account.device_manager.device_map:
                return True
        else:
            return True
        return False
    
    def get_aggregated_device_map(self) -> dict[str, XTDevice]:
        aggregated_list: dict[str, XTDevice] = {}
        device_maps = self._get_available_device_maps()
        for device_map in device_maps:
            for device_id in device_map:
                if device_id not in aggregated_list:
                    aggregated_list[device_id] = XTDevice.from_customer_device(device_map[device_id])
        return aggregated_list
    
    def unload(self):
        LOGGER.warning("UNLOAD")
        if self.sharing_account and not self.iot_account:
            #Only call the unload of the Sharing Manager if there is no IOT account as this will revoke its credentials
            self.sharing_account.device_manager.user_repository.unload(self.sharing_account.device_manager.terminal_id)
    
    def on_tuya_refresh_mq(self, before_call: bool):
        if not before_call and self.sharing_account:
            self.sharing_account.device_manager.on_external_refresh_mq()
    
    async def on_tuya_setup_entry(self, before_call: bool, hass: HomeAssistant, entry: tuya_integration.TuyaConfigEntry):
        #LOGGER.warning(f"on_tuya_setup_entry {before_call} : {entry.__dict__}")
        if not before_call and self.sharing_account and self.config_entry.title == entry.title:
            hass.config_entries.async_schedule_reload(self.config_entry.entry_id)


    async def on_tuya_unload_entry(self, before_call: bool, hass: HomeAssistant, entry: tuya_integration.TuyaConfigEntry):
        #LOGGER.warning(f"on_tuya_unload_entry {before_call} : {entry.__dict__}")
        if not before_call and self.sharing_account and self.config_entry.title == entry.title:
            self.reuse_config = False
            self.sharing_account.device_manager.set_overriden_device_manager(None)
            self.sharing_account.device_manager.mq = None
            self.multi_mqtt_queue.sharing_account_mq = None

    async def on_tuya_remove_entry(self, before_call: bool, hass: HomeAssistant, entry: tuya_integration.TuyaConfigEntry):
        #LOGGER.warning(f"on_tuya_remove_entry {before_call} : {entry.__dict__}")
        if not before_call and self.sharing_account and self.config_entry.title == entry.title:
            self.reuse_config = False
            self.sharing_account.device_manager.set_overriden_device_manager(None)
            self.sharing_account.device_manager.mq = None
            self.multi_mqtt_queue.sharing_account_mq = None
            self.sharing_account.device_manager.refresh_mq()
    
    def refresh_mq(self):
        if self.sharing_account:
            self.sharing_account.device_manager.refresh_mq()
    
    def register_device_descriptors(self, name: str, descriptors):
        descriptors_with_vs = {}
        for category in descriptors:
            decription_list: list = []
            for description in descriptors[category]:
                if hasattr(description, "virtual_state") and description.virtual_state is not None:
                    decription_list.append(description)
            if len(decription_list) > 0:
                descriptors_with_vs[category] = tuple(decription_list)
        if len(descriptors_with_vs) > 0:
            self.descriptors[name] = descriptors_with_vs
            for device in self.get_aggregated_device_map().values():
                self.apply_init_virtual_states(device)

    def get_category_virtual_states(self,category: str) -> list[DescriptionVirtualState]:
        to_return = []
        for virtual_state in VirtualStates:
            for descriptor in self.descriptors.values():
                if (descriptions := descriptor.get(category)):
                    for description in descriptions:
                        if description.virtual_state is not None and description.virtual_state & virtual_state.value:
                            # This virtual_state is applied to this key, let's return it
                            found_virtual_state = DescriptionVirtualState(description.key, virtual_state.name, virtual_state.value, description.vs_copy_to_state)
                            to_return.append(found_virtual_state)
        return to_return
    
    def remove_device_listeners(self) -> None:
        if self.multi_device_listener.iot_account_device_listener:
            self.iot_account.device_manager.remove_device_listener(self.multi_device_listener.iot_account_device_listener)
        if self.multi_device_listener.sharing_account_device_listener:
            self.sharing_account.device_manager.remove_device_listener(self.multi_device_listener.sharing_account_device_listener)

    def get_device_properties(self, device: XTDevice) -> XTDeviceProperties:
        dev_props = XTDeviceProperties()
        if self.iot_account:
            dev_props = self.iot_account.device_manager.get_device_properties(device)
        
        return dev_props
    
    def _read_dpId_from_code(self, code: str, device: XTDevice) -> int | None:
        if not hasattr(device, "local_strategy"):
            return None
        for dpId in device.local_strategy:
            if device.local_strategy[dpId]["status_code"] == code:
                return dpId
        return None
    def _read_code_from_dpId(self, dpId: int, device: XTDevice) -> str | None:
        if dp_id_item := device.local_strategy.get(dpId, None):
            return dp_id_item["status_code"]
        return None
    
    def _get_empty_local_strategy_dp_id(self, device: XTDevice) -> int | None:
        if not hasattr(device, "local_strategy"):
            return None
        base_id = 10000
        while True:
            if base_id in device.local_strategy:
                base_id += 1
                continue
            return base_id

    def apply_init_virtual_states(self, device: XTDevice):
        #WARNING, this method might be called multiple times for the same device, make sure it doesn't
        #fail upon multiple successive calls
        virtual_states = self.get_category_virtual_states(device.category)
        for virtual_state in virtual_states:
            if virtual_state.virtual_state_value == VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME:
                if virtual_state.key in device.status:
                    if virtual_state.key in device.status_range:
                        for vs_new_code in virtual_state.vs_copy_to_state:
                            new_code = str(vs_new_code)
                            device.status[new_code] = copy.deepcopy(device.status[virtual_state.key])
                            device.status_range[new_code] = copy.deepcopy(device.status_range[virtual_state.key])
                            device.status_range[new_code].code = new_code
                            if not self._read_dpId_from_code(new_code, device):
                                if dp_id := self._read_dpId_from_code(virtual_state.key, device):
                                    if new_dp_id := self._get_empty_local_strategy_dp_id(device):
                                        new_local_strategy = copy.deepcopy(device.local_strategy[dp_id])
                                        new_local_strategy["status_code"] = new_code
                                        device.local_strategy[new_dp_id] = new_local_strategy
                    if virtual_state.key in device.function:
                        for vs_new_code in virtual_state.vs_copy_to_state:
                            new_code = str(vs_new_code)
                            device.status[new_code] = copy.deepcopy(device.status[virtual_state.key])
                            device.function[new_code] = copy.deepcopy(device.function[virtual_state.key])
                            device.function[new_code].code = new_code
                            if not self._read_dpId_from_code(new_code, device):
                                if dp_id := self._read_dpId_from_code(virtual_state.key, device):
                                    if new_dp_id := self._get_empty_local_strategy_dp_id(device):
                                        new_local_strategy = copy.deepcopy(device.local_strategy[dp_id])
                                        new_local_strategy["status_code"] = new_code
                                        device.local_strategy[new_dp_id] = new_local_strategy

    def allow_virtual_devices_not_set_up(self, device: XTDevice):
        if not device.id.startswith("vdevo"):
            return
        if not getattr(device, "set_up", True):
            setattr(device, "set_up", True)
    
    def _get_devices_from_device_id(self, device_id: str) -> list[XTDevice] | None:
        return_list = []
        device_maps = self._get_available_device_maps()
        for device_map in device_maps:
            if device_id in device_map:
                return_list.append(device_map[device_id])
        return return_list

    def _read_code_dpid_value_from_state(self, device_id: str, state, fail_if_dpid_not_found = True, fail_if_code_not_found = True):
        devices = self._get_devices_from_device_id(device_id)
        code = None
        dpId = None
        value = None
        for device in devices:
            if not code and "code" in state:
                dpId = self._read_dpId_from_code(state["code"], device)
            if not dpId and "dpId" in state:
                code = self._read_code_from_dpId(state["dpId"], device)
            if not value and "value" in state:
                value = state["value"]
            if code is not None and dpId is not None and value is not None:
                return code, dpId, value, True
        if code is None and fail_if_code_not_found:
            LOGGER.warning(f"_read_code_value_from_state FAILED => {device.id} <=> {device.name} <=> {state} <=> {device.local_strategy}")
            return None, None, None, False
        if dpId is None and fail_if_dpid_not_found:
            LOGGER.warning(f"_read_code_value_from_state FAILED => {device.id} <=> {device.name} <=> {state} <=> {device.local_strategy}")
            return None, None, None, False
        return code, dpId, value, True

    def convert_device_report_status_list(self, device_id: str, status_in: list) -> list:
        status = copy.deepcopy(status_in)
        devices = self._get_devices_from_device_id(device_id)
        if len(devices) == 0:
            return []
        for item in status:
            for device in devices:
                code, dpId, value, result_ok = self._read_code_dpid_value_from_state(device.id, item)
                if result_ok:
                    item["code"] = code
                    item["value"] = value
                    if dpId:
                        item["dpId"] = dpId
                    break
                else:
                    LOGGER.warning(f"convert_device_report_status_list code retrieval failed => {item} <=> {device.name} <=>{device_id}")
        return status
    
    def apply_virtual_states_to_status_list(self, device: XTDevice, status_in: list) -> list:
        status = copy.deepcopy(status_in)
        virtual_states = self.get_category_virtual_states(device.category)
        for virtual_state in virtual_states:
            if virtual_state.virtual_state_value == VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME:
                for item in status:
                    code, dpId, value, result_ok = self._read_code_dpid_value_from_state(device.id, item)
                    if result_ok and code == virtual_state.key:
                        for state_name in virtual_state.vs_copy_to_state:
                            new_status = {"code": str(state_name), "value": copy.deepcopy(value), "dpId": dpId}
                            status.append(new_status)
            
            if virtual_state.virtual_state_value == VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD:
                if virtual_state.key not in device.status or device.status[virtual_state.key] is None:
                    device.status[virtual_state.key] = 0
                if virtual_state.key in device.status:
                    for item in status:
                        code, dpId, value, result_ok = self._read_code_dpid_value_from_state(device.id, item, False, True)
                        if result_ok and code == virtual_state.key:
                            item["value"] += device.status[virtual_state.key]
                            continue
        return status

    def on_message_from_tuya_iot(self, msg:str):
        self.on_message(MESSAGE_SOURCE_TUYA_IOT, msg)
    
    def on_message_from_tuya_sharing(self, msg:str):
        self.on_message(MESSAGE_SOURCE_TUYA_SHARING, msg)

    def on_message(self, source: str, msg: str):
        dev_id = self._get_device_id_from_message(msg)
        if not dev_id:
            LOGGER.warning(f"dev_id {dev_id} not found!")
            return
        
        new_message = self._convert_message_for_all_accounts(msg)
        if self.sharing_account and dev_id in self.sharing_account.device_ids:
            if source == MESSAGE_SOURCE_TUYA_SHARING:
                self.sharing_account.device_manager.on_message(new_message)
        elif self.iot_account and dev_id in self.iot_account.device_ids:
            if source == MESSAGE_SOURCE_TUYA_IOT:
                self.iot_account.device_manager.on_message(new_message)
        
        #DEBUG
        device = self.get_aggregated_device_map()[dev_id]
        LOGGER.warning(f"Device status after : {device.status}")
        #END DEBUG

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

    def send_commands(
            self, device_id: str, commands: list[dict[str, Any]]
    ):
        open_api_regular_commands = []
        regular_commands = []
        property_commands = []
        device_map = self.get_aggregated_device_map()
        if device := device_map.get(device_id, None):
            for command in commands:
                for dp_item in device.local_strategy.values():
                    code = dp_item.get("status_code", None)
                    value = command["value"]
                    if command["code"] == code:
                        if not dp_item.get("use_open_api", False):
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
                self.sharing_account.device_manager.send_commands(device_id, regular_commands)
            if open_api_regular_commands:
                self.iot_account.device_manager.send_commands(device_id, open_api_regular_commands)
            if property_commands:
                self.iot_account.device_manager.send_property_update(device_id, property_commands)
            return
        self.sharing_account.device_manager.send_commands(device_id, commands)