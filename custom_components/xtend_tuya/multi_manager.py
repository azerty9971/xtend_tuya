from __future__ import annotations
import requests
from typing import NamedTuple, Optional, Any
from types import SimpleNamespace

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

from .import_stub import (
    MultiManager,
    XTDeviceStatusRange,
    XTDeviceFunction,
    XTDeviceProperties,
)

from .util import (
    get_domain_config_entries,
    get_overriden_config_entry,
    get_tuya_integration_runtime_data,
    get_overriden_tuya_integration_runtime_data,
    prepare_value_for_property_update,
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

type XTConfigEntry = ConfigEntry[HomeAssistantXTData]

class HomeAssistantXTData(NamedTuple):
    """Tuya data stored in the Home Assistant data object."""

    multi_manager: MultiManager
    reuse_config: bool = False

class XTDeviceProperties(SimpleNamespace):  # noqa: F811
    local_strategy: dict[int, dict[str, Any]] = {}
    status: dict[str, Any] = {}
    function: dict[str, XTDeviceFunction] = {}
    status_range: dict[str, XTDeviceStatusRange] = {}

class XTDeviceStatusRange:  # noqa: F811
    code: str
    type: str
    values: str

class XTDeviceFunction:  # noqa: F811
    code: str
    desc: str
    name: str
    type: str
    values: dict[str, Any]

class XTDevice(SimpleNamespace):
    id: str
    name: str
    local_key: str
    category: str
    product_id: str
    product_name: str
    sub: bool
    uuid: str
    asset_id: str
    online: bool
    icon: str
    ip: str
    time_zone: str
    active_time: int
    create_time: int
    update_time: int
    set_up: Optional[bool] = False
    support_local: Optional[bool] = False
    local_strategy: dict[int, dict[str, Any]] = {}

    status: dict[str, Any] = {}
    function: dict[str, XTDeviceFunction] = {}
    status_range: dict[str, XTDeviceStatusRange] = {}

    def __eq__(self, other):
        """If devices are the same one."""
        return self.id == other.id

    def from_customer_device(device: CustomerDevice):
        return XTDevice(**device)

class TuyaIOTData(NamedTuple):
    device_manager: XTTuyaDeviceManager
    mq: TuyaOpenMQ
    device_ids: set[str]
    device_listener: XTDeviceListener
    home_manager: TuyaHomeManager

class TuyaSharingData(NamedTuple):
    device_manager: DeviceManager

class TuyaIntegrationRuntimeData(NamedTuple):
    device_manager: TuyaSharingManager
    generic_runtime_data: any


class MultiManager:  # noqa: F811
    def __init__(self, hass: HomeAssistant, entry: XTConfigEntry) -> None:
        self.sharing_account: TuyaSharingData = None
        self.iot_account: TuyaIOTData = None
        self.reuse_config: bool = False
        self.descriptors = {}

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
        sharing_device_manager.home_repository = HomeRepository(sharing_device_manager.customer_api)
        sharing_device_manager.device_repository = XTDeviceRepository(sharing_device_manager.customer_api, sharing_device_manager)
        sharing_device_manager.device_listeners = set()
        sharing_device_manager.scene_repository = SceneRepository(sharing_device_manager.customer_api)
        sharing_device_manager.user_repository = UserRepository(sharing_device_manager.customer_api)
        listener = DeviceListener(hass, sharing_device_manager)
        sharing_device_manager.add_device_listener(listener)
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
        mq.start()
        device_manager = XTTuyaDeviceManager(self, api, mq)
        device_ids: set[str] = set()
        device_listener = XTDeviceListener(hass, device_manager, device_ids)
        home_manager = TuyaHomeManager(api, mq, device_manager)
        device_manager.add_device_listener(device_listener)
        return TuyaIOTData(device_manager=device_manager,mq=mq,device_ids=device_ids,device_listener=device_listener, home_manager=home_manager)
    
    def update_device_cache(self):
        if self.sharing_account:
            self.sharing_account.device_manager.update_device_cache()
        if self.iot_account:
            self.iot_account.home_manager.update_device_cache()
    
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
        aggregated_list = dict[str, XTDevice]
        if self.sharing_account:
            for device_id in self.sharing_account.device_manager.device_map:
                aggregated_list[device_id] = XTDevice.from_customer_device(self.sharing_account.device_manager.device_map[device_id])
        if self.iot_account:
            for device_id in self.iot_account.device_manager.device_map:
                aggregated_list[device_id] = XTDevice.from_customer_device(self.iot_account.device_manager.device_map[device_id])
    
    def unload(self):
        if self.sharing_account:
            self.sharing_account.device_manager.user_repository.unload(self.sharing_account.device_manager.terminal_id)
    
    def refresh_mq(self):
        if self.sharing_account:
            self.sharing_account.device_manager.refresh_mq()
    
    def register_device_descriptors(self, name: str, descriptors):
        self.descriptors[name] = descriptors

    def get_category_virtual_states(self,category: str) -> list[DescriptionVirtualState]:
        to_return = []
        for virtual_state in VirtualStates:
            for descriptor in self.descriptors.values():
                if (descriptions := descriptor.get(category)):
                    for description in descriptions:
                        if description.virtualstate is not None and description.virtualstate & virtual_state.value:
                            # This VirtualState is applied to this key, let's return it
                            found_virtual_state = DescriptionVirtualState(description.key, virtual_state.name, virtual_state.value, description.vs_copy_to_state)
                            to_return.append(found_virtual_state)
        return to_return
    
    def get_device_properties(self, device: XTDevice) -> XTDeviceProperties:
        dev_props = XTDeviceProperties()
        if self.iot_account:
            dev_props = self.iot_account.device_manager.get_device_properties(device)
        
        return dev_props
    
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