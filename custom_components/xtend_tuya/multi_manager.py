from __future__ import annotations
import requests
import copy
from typing import NamedTuple, Optional, Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady
from homeassistant.config_entries import ConfigEntry

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
    prepare_value_for_property_update
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
    device_ids: set[str]
    device_listener: XTDeviceListener
    home_manager: TuyaHomeManager

class TuyaSharingData(NamedTuple):
    device_manager: DeviceManager

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
    def __init__(self, hass: HomeAssistant, entry: XTConfigEntry) -> None:
        self.sharing_account: TuyaSharingData = None
        self.iot_account: TuyaIOTData = None
        self.reuse_config: bool = False
        self.descriptors = {}
        self.multi_mqtt_queue: MultiMQTTQueue = MultiMQTTQueue(self)
        self.multi_device_listener: MultiDeviceListener = MultiDeviceListener(self)

    @property
    def device_map(self):
        return self.get_aggregated_device_map()
    
    @property
    def mq(self):
        return self.multi_mqtt_queue

    async def setup_entry(self, hass: HomeAssistant, entry: XTConfigEntry) -> None:
        if (account := await self.get_iot_account(hass, entry)):
            self.iot_account = account
        if (account := await self.get_sharing_account(hass,entry)):
            self.sharing_account = account


    async def get_sharing_account(self, hass: HomeAssistant, entry: XTConfigEntry) -> TuyaSharingData | None:
        #See if our current entry is an override of a Tuya integration entry
        tuya_integration_runtime_data = get_overriden_tuya_integration_runtime_data(hass, entry)
        if tuya_integration_runtime_data:
            #We are using an override of the Tuya integration
            sharing_device_manager = DeviceManager(multi_manager=self, other_device_manager=tuya_integration_runtime_data.device_manager)
            sharing_device_manager.terminal_id  = tuya_integration_runtime_data.device_manager.terminal_id
            sharing_device_manager.mq           = tuya_integration_runtime_data.device_manager.mq
            sharing_device_manager.customer_api = tuya_integration_runtime_data.device_manager.customer_api
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
        sharing_device_manager.device_listeners = set()
        sharing_device_manager.scene_repository = SceneRepository(sharing_device_manager.customer_api)
        sharing_device_manager.user_repository = UserRepository(sharing_device_manager.customer_api)
        self.multi_device_listener.sharing_account_device_listener = DeviceListener(hass, sharing_device_manager)
        sharing_device_manager.add_device_listener(self.multi_device_listener.sharing_account_device_listener)
        return TuyaSharingData(device_manager=sharing_device_manager)

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
        device_ids: set[str] = set()
        self.multi_device_listener.iot_account_device_listener = XTDeviceListener(hass, device_manager, device_ids, self)
        home_manager = TuyaHomeManager(api, mq, device_manager)
        device_manager.add_device_listener(self.multi_device_listener.iot_account_device_listener)
        return TuyaIOTData(
            device_manager=device_manager,
            mq=mq,device_ids=device_ids,
            device_listener=self.multi_device_listener.iot_account_device_listener, 
            home_manager=home_manager)
    
    def update_device_cache(self):
        if self.sharing_account:
            self.sharing_account.device_manager.update_device_cache()
        if self.iot_account:
            self.iot_account.home_manager.update_device_cache()
        self._merge_devices_from_multiple_sources()
    
    def _merge_devices_from_multiple_sources(self):
        if not ( self.sharing_account and self.iot_account ):
            return
        
        #Merge the device function, status_range and status between managers
        device_maps = [self.sharing_account.device_manager.device_map, self.iot_account.device_manager.device_map]
        aggregated_device_list = self.get_aggregated_device_map()
        for device in aggregated_device_list.values():
            to_be_merged = []
            for device_map in device_maps:
                if device.id in device_map:
                    for prev_device in to_be_merged:
                        self._merge_devices(device, prev_device)
                        self._merge_devices(prev_device, device)
                    to_be_merged.append(device)
        for device_map in device_maps:
            device_map.update(aggregated_device_list)
            
    def _merge_devices(self, device1: XTDevice, device2: XTDevice):
        device1.status_range.update(device2.status_range)
        device1.function.update(device2.function)
        device1.status.update(device2.status)
        if hasattr(device1, "local_strategy") and hasattr(device2, "local_strategy"):
            device1.local_strategy.update(device2.local_strategy)

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
        if self.sharing_account:
            for device_id in self.sharing_account.device_manager.device_map:
                aggregated_list[device_id] = XTDevice.from_customer_device(self.sharing_account.device_manager.device_map[device_id])
        if self.iot_account:
            for device_id in self.iot_account.device_manager.device_map:
                aggregated_list[device_id] = XTDevice.from_customer_device(self.iot_account.device_manager.device_map[device_id])
        return aggregated_list
    
    def unload(self):
        if self.sharing_account:
            self.sharing_account.device_manager.user_repository.unload(self.sharing_account.device_manager.terminal_id)
    
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
    
    def apply_init_virtual_states(self, device: XTDevice):
        #LOGGER.warning(f"apply_init_virtual_states BEFORE => {device.status} <=> {device.status_range}")
        virtual_states = self.get_category_virtual_states(device.category)
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

    def allow_virtual_devices_not_set_up(self, device: XTDevice):
        if not device.id.startswith("vdevo"):
            return
        if not getattr(device, "set_up", True):
            setattr(device, "set_up", True)

    def on_message(self, msg: str):
        LOGGER.warning(f"on_message => {msg}")
        if self.sharing_account:
            self.sharing_account.device_manager.on_message(msg)
        if self.iot_account:
            new_message = self._convert_message_for_iot_account(msg)
            LOGGER.warning(f"new_message => {new_message}")
            self.iot_account.device_manager.on_message(new_message)

    def _convert_message_for_iot_account(self, msg: str) -> str:
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
        if device_id in device_map:
            device = device_map.get(device_id, None)
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
                    self.sharing_account.device_manager.send_commands(device_id, regular_commands)
                if open_api_regular_commands:
                    self.iot_account.device_manager.send_commands(device_id, open_api_regular_commands)
                if property_commands:
                    self.iot_account.device_manager.send_property_update(device_id, property_commands)
                return
        self.sharing_account.device_manager.send_commands(device_id, commands)