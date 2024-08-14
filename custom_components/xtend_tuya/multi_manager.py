from __future__ import annotations
import requests
import copy
from typing import NamedTuple, Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.config_entries import ConfigEntry
import homeassistant.components.tuya as tuya_integration
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import EntityDescription

from tuya_iot import (
    AuthType,
    TuyaOpenAPI,
    TuyaOpenMQ,
)
from tuya_iot.device import (
    PROTOCOL_DEVICE_REPORT,
    PROTOCOL_OTHER,
)

from tuya_sharing import (
    SharingDeviceListener,
)
from tuya_sharing.customerapi import (
    CustomerTokenInfo,
    CustomerApi,
)
from tuya_sharing.home import (
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
    TUYA_CLIENT_ID,
    TUYA_DISCOVERY_NEW,
    TUYA_DISCOVERY_NEW_ORIG,
    TUYA_HA_SIGNAL_UPDATE_ENTITY,
    TUYA_HA_SIGNAL_UPDATE_ENTITY_ORIG,
    VirtualStates,
    VirtualFunctions,
    DescriptionVirtualState,
    DescriptionVirtualFunction,
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_APP_TYPE,
    CONF_AUTH_TYPE,
    CONF_COUNTRY_CODE,
    CONF_ENDPOINT_OT,
    CONF_PASSWORD,
    CONF_USERNAME,
    MESSAGE_SOURCE_TUYA_IOT,
    MESSAGE_SOURCE_TUYA_SHARING,
)

from .import_stub import (
    MultiManager,
    XTConfigEntry,
)

from .shared_classes import (
    XTDeviceProperties,
    XTDevice,
)

from .util import (
    get_overriden_tuya_integration_runtime_data,
    get_tuya_integration_runtime_data,
    prepare_value_for_property_update,
    merge_iterables,
    append_lists,
)

from .tuya_decorators import (
    decorate_tuya_manager,
)

from .xt_tuya_sharing import (
    XTSharingDeviceManager,
    XTSharingTokenListener,
    XTSharingDeviceRepository,
)
from .xt_tuya_iot import (
    XTIOTDeviceManager,
    XTIOTHomeManager,
)

class HomeAssistantXTData(NamedTuple):
    """Tuya data stored in the Home Assistant data object."""

    multi_manager: MultiManager
    reuse_config: bool = False
    listener: SharingDeviceListener = None

    @property
    def manager(self) -> MultiManager:
        return self.multi_manager

class TuyaIOTData(NamedTuple):
    device_manager: XTIOTDeviceManager
    mq: TuyaOpenMQ
    device_ids: list[str] #List of device IDs that are managed by the manager before the managers device merging process
    home_manager: XTIOTHomeManager

class TuyaSharingData(NamedTuple):
    device_manager: XTSharingDeviceManager
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
    def __init__(self, hass: HomeAssistant, multi_manager: MultiManager) -> None:
        self.multi_manager = multi_manager
        self.hass = hass

    def update_device(self, device: XTDevice):
        devices = self.multi_manager.get_devices_from_device_id(device.id)
        for cur_device in devices:
            XTDevice.copy_data_from_device(device, cur_device)
        #if self.multi_manager.reuse_config:
        dispatcher_send(self.hass, f"{TUYA_HA_SIGNAL_UPDATE_ENTITY_ORIG}_{device.id}")
        dispatcher_send(self.hass, f"{TUYA_HA_SIGNAL_UPDATE_ENTITY}_{device.id}")

    def add_device(self, device: XTDevice):
        self.hass.add_job(self.async_remove_device, device.id)
        if self.multi_manager.reuse_config:
            dispatcher_send(self.hass, TUYA_DISCOVERY_NEW_ORIG, [device.id])
        dispatcher_send(self.hass, TUYA_DISCOVERY_NEW, [device.id])

    def remove_device(self, device_id: str):
        #log_stack("DeviceListener => async_remove_device")
        device_registry = dr.async_get(self.hass)
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN_ORIG, device_id), (DOMAIN, device_id)}
        )
        if device_entry is not None:
            device_registry.async_remove_device(device_entry.id)
    
    @callback
    def async_remove_device(self, device_id: str) -> None:
        """Remove device from Home Assistant."""
        #log_stack("DeviceListener => async_remove_device")
        device_registry = dr.async_get(self.hass)
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN_ORIG, device_id), (DOMAIN, device_id)}
        )
        if device_entry is not None:
            device_registry.async_remove_device(device_entry.id)
    
class MultiManager:  # noqa: F811
    def __init__(self, hass: HomeAssistant, entry: XTConfigEntry) -> None:
        self.sharing_account: TuyaSharingData = None
        self.iot_account: TuyaIOTData = None
        self.reuse_config: bool = False
        self.descriptors_with_virtual_state = {}
        self.descriptors_with_virtual_function = {}
        self.multi_mqtt_queue: MultiMQTTQueue = MultiMQTTQueue(self)
        self.multi_device_listener: MultiDeviceListener = MultiDeviceListener(hass, self)
        self.config_entry = entry
        self.hass = hass

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
            sharing_device_manager = XTSharingDeviceManager(multi_manager=self, other_device_manager=tuya_integration_runtime_data.device_manager)
            sharing_device_manager.terminal_id      = tuya_integration_runtime_data.device_manager.terminal_id
            sharing_device_manager.mq               = tuya_integration_runtime_data.device_manager.mq
            sharing_device_manager.customer_api     = tuya_integration_runtime_data.device_manager.customer_api
            tuya_integration_runtime_data.device_manager.device_listeners.clear()
            #self.convert_tuya_devices_to_xt(tuya_integration_runtime_data.device_manager)
            self.reuse_config = True
        else:
            #We are using XT as a standalone integration
            sharing_device_manager = XTSharingDeviceManager(multi_manager=self, other_device_manager=None)
            token_listener = XTSharingTokenListener(hass, entry)
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
        sharing_device_manager.device_repository = XTSharingDeviceRepository(sharing_device_manager.customer_api, sharing_device_manager, self)
        sharing_device_manager.scene_repository = SceneRepository(sharing_device_manager.customer_api)
        sharing_device_manager.user_repository = UserRepository(sharing_device_manager.customer_api)
        sharing_device_manager.add_device_listener(self.multi_device_listener)
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
        mq = TuyaOpenMQ(api)
        self.multi_mqtt_queue.iot_account_mq = mq
        mq.start()
        device_manager = XTIOTDeviceManager(self, api, mq)
        device_ids: list[str] = list()
        home_manager = XTIOTHomeManager(api, mq, device_manager, self)
        device_manager.add_device_listener(self.multi_device_listener)
        return TuyaIOTData(
            device_manager=device_manager,
            mq=mq,
            device_ids=device_ids,
            home_manager=home_manager)
    
    def update_device_cache(self):
        if self.sharing_account:
            self.sharing_account.device_manager.update_device_cache()
            new_device_ids: list[str] = [device_id for device_id in self.sharing_account.device_manager.device_map]
            self.sharing_account.device_ids.clear()
            self.sharing_account.device_ids.extend(new_device_ids)
        if self.iot_account:
            self.iot_account.home_manager.update_device_cache()
            new_device_ids: list[str] = [device_id for device_id in self.iot_account.device_manager.device_map]
            self.iot_account.device_ids.clear()
            self.iot_account.device_ids.extend(new_device_ids)
        self._merge_devices_from_multiple_sources()
    
    def convert_tuya_devices_to_xt(self, manager):
        for dev_id in manager.device_map:
            manager.device_map[dev_id] = XTDevice.from_compatible_device(manager.device_map[dev_id])

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
        #Merge the device function, status_range and status between managers
        device_maps = self._get_available_device_maps()
        aggregated_device_list = self.device_map
        for device in aggregated_device_list.values():
            to_be_merged: list[XTDevice] = []
            devices = self.get_devices_from_device_id(device.id)
            for current_device in devices:
                for prev_device in to_be_merged:
                    self._merge_devices(current_device, prev_device)
                    to_be_merged.append(current_device)
        for device_map in device_maps:
            merge_iterables(device_map, aggregated_device_list)
        
    def _merge_devices(self, receiving_device: XTDevice, giving_device: XTDevice):
        merge_iterables(receiving_device.status_range, giving_device.status_range)
        merge_iterables(receiving_device.function, giving_device.function)
        merge_iterables(receiving_device.status, giving_device.status)
        if hasattr(receiving_device, "local_strategy") and hasattr(giving_device, "local_strategy"):
            merge_iterables(receiving_device.local_strategy, giving_device.local_strategy)
        if hasattr(receiving_device, "model") and hasattr(giving_device, "model"):
            if receiving_device.model == "" and giving_device.model != "":
                receiving_device.model = copy.deepcopy(giving_device.model)
            if giving_device.model == "" and receiving_device.model != "":
                giving_device.model = copy.deepcopy(receiving_device.model)
    
    def get_aggregated_device_map(self) -> dict[str, XTDevice]:
        aggregated_list: dict[str, XTDevice] = {}
        device_maps = self._get_available_device_maps()
        for device_map in device_maps:
            for device_id in device_map:
                if device_id not in aggregated_list:
                    aggregated_list[device_id] = device_map[device_id]
        return aggregated_list
    
    def unload(self):
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
        if before_call:
            #If before the call, we need to add the regular device listener back
            runtime_data = get_tuya_integration_runtime_data(hass, entry, DOMAIN_ORIG)
            runtime_data.device_manager.add_device_listener(runtime_data.device_listener)
        else:
            if self.sharing_account and self.config_entry.title == entry.title:
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
        descriptors_with_vf = {}
        for category in descriptors:
            description_list_vs: list = []
            description_list_vf: list = []
            category_item = descriptors[category]
            if isinstance(category_item, tuple):
                for description in category_item:
                    if hasattr(description, "virtual_state") and description.virtual_state is not None:
                        description_list_vs.append(description)
                    if hasattr(description, "virtual_function") and description.virtual_function is not None:
                        description_list_vf.append(description)
                    
            elif isinstance(category_item, EntityDescription):
                #category is directly a descriptor
                if hasattr(category_item, "virtual_state") and category_item.virtual_state is not None:
                    description_list_vs.append(category_item)
                if hasattr(category_item, "virtual_function") and category_item.virtual_function is not None:
                    description_list_vf.append(category_item)

            if len(description_list_vs) > 0:
                    descriptors_with_vs[category] = tuple(description_list_vs)
            if len(description_list_vf) > 0:
                    descriptors_with_vf[category] = tuple(description_list_vf)
        if len(descriptors_with_vs) > 0:
            self.descriptors_with_virtual_state[name] = descriptors_with_vs
            for device_id in self.device_map:
                devices = self.get_devices_from_device_id(device_id)
                for device in devices:
                    self.apply_init_virtual_states(device)

        if len(descriptors_with_vf) > 0:
            self.descriptors_with_virtual_function[name] = descriptors_with_vf

    def get_category_virtual_states(self,category: str) -> list[DescriptionVirtualState]:
        to_return = []
        for virtual_state in VirtualStates:
            for descriptor in self.descriptors_with_virtual_state.values():
                if (descriptions := descriptor.get(category)):
                    for description in descriptions:
                        if description.virtual_state is not None and description.virtual_state & virtual_state.value:
                            # This virtual_state is applied to this key, let's return it
                            found_virtual_state = DescriptionVirtualState(description.key, virtual_state.name, virtual_state.value, description.vs_copy_to_state)
                            to_return.append(found_virtual_state)
        return to_return
    
    def get_category_virtual_functions(self,category: str) -> list[DescriptionVirtualFunction]:
        to_return = []
        for virtual_function in VirtualFunctions:
            for descriptor in self.descriptors_with_virtual_function.values():
                if (descriptions := descriptor.get(category)):
                    for description in descriptions:
                        if description.virtual_function is not None and description.virtual_function & virtual_function.value:
                            # This virtual_state is applied to this key, let's return it
                            found_virtual_function = DescriptionVirtualFunction(description.key, virtual_function.name, virtual_function.value, description.vf_reset_state)
                            to_return.append(found_virtual_function)
        return to_return
    
    def remove_device_listeners(self) -> None:
        if self.iot_account:
            self.iot_account.device_manager.remove_device_listener(self.multi_device_listener)
        if self.sharing_account:
            self.sharing_account.device_manager.remove_device_listener(self.multi_device_listener)

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
                            if device.status.get(new_code, None) is None:
                                device.status[new_code] = copy.deepcopy(device.status[virtual_state.key])
                            device.status_range[new_code] = copy.deepcopy(device.status_range[virtual_state.key])
                            device.status_range[new_code].code = new_code
                            if not self._read_dpId_from_code(new_code, device):
                                if dp_id := self._read_dpId_from_code(virtual_state.key, device):
                                    if new_dp_id := self._get_empty_local_strategy_dp_id(device):
                                        new_local_strategy = copy.deepcopy(device.local_strategy[dp_id])
                                        if "config_item" in new_local_strategy:
                                            new_local_strategy_config_item = new_local_strategy["config_item"]
                                            if "statusFormat" in new_local_strategy_config_item and virtual_state.key in new_local_strategy_config_item["statusFormat"]:
                                                new_local_strategy_config_item["statusFormat"] = new_local_strategy_config_item["statusFormat"].replace(virtual_state.key, new_code)
                                        new_local_strategy["status_code"] = new_code
                                        device.local_strategy[new_dp_id] = new_local_strategy
                    if virtual_state.key in device.function:
                        for vs_new_code in virtual_state.vs_copy_to_state:
                            new_code = str(vs_new_code)
                            if device.status.get(new_code, None) is None:
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
    
    def get_devices_from_device_id(self, device_id: str) -> list[XTDevice] | None:
        return_list = []
        device_maps = self._get_available_device_maps()
        for device_map in device_maps:
            if device_id in device_map:
                return_list.append(device_map[device_id])
        return return_list

    def _read_code_dpid_value_from_state(self, device_id: str, state, fail_if_dpid_not_found = True, fail_if_code_not_found = True):
        devices = self.get_devices_from_device_id(device_id)
        code = None
        dpId = None
        value = None
        if "value" in state:
            value = state["value"]
        for device in devices:
            if code is None and "code" in state:
                code = state["code"]
                dpId = self._read_dpId_from_code(state["code"], device)
            if dpId is None and "dpId" in state:
                if device_id == "bfd96de2b508052bb3dzco":
                    LOGGER.warning("Found dpId")
                dpId = state["dpId"]
                code = self._read_code_from_dpId(state["dpId"], device)
            if dpId is None and code is None and "dpId" not in state and "code" not in state:
                for temp_dpId in state:
                    temp_code = self._read_code_from_dpId(int(temp_dpId), device)
                    if temp_code is not None:
                        dpId = int(temp_dpId)
                        code = temp_code
                        value = state[temp_dpId]

            if code is not None and dpId is not None:
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
        for item in status:
            code, dpId, value, result_ok = self._read_code_dpid_value_from_state(device_id, item)
            if result_ok:
                item["code"] = code
                item["dpId"] = dpId
                item["value"] = value
            else:
                LOGGER.warning(f"convert_device_report_status_list code retrieval failed => {item} <=>{device_id}")
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
                            code, dpId, value, result_ok = self._read_code_dpid_value_from_state(device.id, {"code": str(state_name), "value": value})
                            if result_ok:
                                new_status = {"code": code, "value": copy.copy(value), "dpId": dpId}
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
        
        LOGGER.debug(f"on_message from {source} : {msg}")
        
        new_message = self._convert_message_for_all_accounts(msg)
        allowed_source = self.get_allowed_source(dev_id, source)
        if source == MESSAGE_SOURCE_TUYA_SHARING and source == allowed_source:
            self.sharing_account.device_manager.on_message(new_message)
        elif source == MESSAGE_SOURCE_TUYA_IOT and source == allowed_source:
            self.iot_account.device_manager.on_message(new_message)

    def get_allowed_source(self, dev_id: str, original_source: str) -> str | None:
        """if dev_id.startswith("vdevo"):
            return MESSAGE_SOURCE_TUYA_IOT"""
        in_iot = False
        if self.iot_account and dev_id in self.iot_account.device_ids:
            in_iot = True
        in_sharing = False
        if self.sharing_account and dev_id in self.sharing_account.device_ids:
            in_sharing = True

        if in_iot and in_sharing:
            return MESSAGE_SOURCE_TUYA_SHARING
        elif in_iot:
            return MESSAGE_SOURCE_TUYA_IOT
        elif in_sharing:
            return MESSAGE_SOURCE_TUYA_SHARING
        return None

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

    def query_scenes(self) -> list:
        return_list = []
        if self.sharing_account:
            temp_list = self.sharing_account.device_manager.query_scenes()
            return_list = append_lists(return_list, temp_list)
        if self.iot_account:
            temp_list = self.iot_account.home_manager.query_scenes()
            return_list = append_lists(return_list, temp_list)
        return return_list

    def send_commands(
            self, device_id: str, commands: list[dict[str, Any]]
    ):
        open_api_regular_commands: list[dict[str, Any]] = []
        regular_commands: list[dict[str, Any]] = []
        property_commands: list[dict[str, Any]] = []
        virtual_function_commands: list[dict[str, Any]] = []
        device_map = self.get_aggregated_device_map()
        if device := device_map.get(device_id, None):
            virtual_function_list = self.get_category_virtual_functions(device.category)
            for command in commands:
                command_code  = command["code"]
                command_value = command["value"]
                LOGGER.debug(f"Base command : {command}")
                vf_found = False
                for virtual_function in virtual_function_list:
                    if (command_code == virtual_function.key or
                        command_code in virtual_function.vf_reset_state):
                        command_dict = {"code": command_code, "value": command_value, "virtual_function": virtual_function}
                        virtual_function_commands.append(command_dict)
                        vf_found = True
                        break
                if vf_found:
                    continue
                for dp_item in device.local_strategy.values():
                    dp_item_code = dp_item.get("status_code", None)
                    if command_code == dp_item_code:
                        if not dp_item.get("use_open_api", False):
                            #command_dict = {"code": code, "value": value}
                            regular_commands.append(command)
                        else:
                            if dp_item.get("property_update", False):
                                command_value = prepare_value_for_property_update(dp_item, command_value)
                                property_dict = {str(dp_item_code): command_value}
                                property_commands.append(property_dict)
                            else:
                                command_dict = {"code": dp_item_code, "value": command_value}
                                open_api_regular_commands.append(command_dict)
                            break
            if virtual_function_commands:
                LOGGER.debug(f"Sending virtual function command : {virtual_function_commands}")
                self._process_virtual_function(device_id, virtual_function_commands)
            if regular_commands:
                LOGGER.debug(f"Sending regular command : {regular_commands}")
                self.sharing_account.device_manager.send_commands(device_id, regular_commands)
            if open_api_regular_commands:
                LOGGER.debug(f"Sending Open API regular command : {open_api_regular_commands}")
                self.iot_account.device_manager.send_commands(device_id, open_api_regular_commands)
            if property_commands:
                LOGGER.debug(f"Sending property command : {property_commands}")
                self.iot_account.device_manager.send_property_update(device_id, property_commands)
            return
        self.sharing_account.device_manager.send_commands(device_id, commands)

    def _process_virtual_function(self, device_id: str, commands: list[dict[str, Any]]):
        devices = self.get_devices_from_device_id(device_id)
        if not devices:
            return
        for command in commands:
            virtual_function: DescriptionVirtualFunction = command["virtual_function"]
            """command_code: str = command["code"]
            command_value: Any = command["value"]"""
            device = None
            if virtual_function.virtual_function_value == VirtualFunctions.FUNCTION_RESET_STATE:
                for state_to_reset in virtual_function.vf_reset_state:
                    for device in devices:
                        if state_to_reset in device.status:
                            device.status[state_to_reset] = 0
                            self.multi_device_listener.update_device(device)
                            break
