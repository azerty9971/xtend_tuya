from __future__ import annotations
import requests
from typing import NamedTuple

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
)

from .tuya_sharing import (
    DeviceManager,
    TokenListener,
    DeviceListener,
    XTDeviceRepository,
)
from .tuya_iot import (
    XTTuyaDeviceManager,
    XTDeviceListener,
    tuya_iot_update_listener,
)

type XTConfigEntry = ConfigEntry[HomeAssistantXTData]

class HomeAssistantXTData(NamedTuple):
    """Tuya data stored in the Home Assistant data object."""

    multi_manager: MultiManager
    reuse_config: bool = False

class XTDevice(CustomerDevice):
    def from_customer_device(device: CustomerDevice):
        return XTDevice(**device)

class TuyaIOTData(NamedTuple):
    device_manager: XTTuyaDeviceManager
    mq: TuyaOpenMQ
    device_ids: set[str]
    device_listener: XTDeviceListener

class TuyaSharingData(NamedTuple):
    device_manager: DeviceManager

class TuyaIntegrationRuntimeData(NamedTuple):
    device_manager: TuyaSharingManager
    generic_runtime_data: any


class MultiManager:  # noqa: F811
    def __init__(self, hass: HomeAssistant, entry: XTConfigEntry) -> None:
        self.sharing_account: TuyaSharingData = None
        self.iot_account: TuyaIOTData = None
        self.reuse_config = False
        self.descriptors = {}
        if (account := self.get_iot_account(hass, entry).__await__()):
            self.iot_account = account
        if (account := self.get_sharing_account(hass,entry).__await__()):
            self.sharing_account = account

    def _get_domain_config_entries(hass: HomeAssistant, domain: str) -> list[ConfigEntry]:
        return hass.config_entries.async_entries(domain,False,False)
    
    def _get_overriden_config_entry(hass: HomeAssistant, entry: XTConfigEntry, other_domain: str) -> ConfigEntry:
        other_domain_config_entries = MultiManager._get_domain_config_entries(other_domain)
        for od_config_entry in other_domain_config_entries:
            if entry.title == od_config_entry.title:
                return od_config_entry
        return None
    
    def _get_tuya_integration_runtime_data(hass: HomeAssistant, entry: ConfigEntry, domain: str) -> TuyaIntegrationRuntimeData | None:
        if not entry:
            return None
        runtime_data = None
        if (
            not hasattr(entry, 'runtime_data') 
            or entry.runtime_data is None
        ):
            #Try to fetch the manager using the old way
            device_manager = None
            if (
                domain in hass.data and
                entry.entry_id in hass.data[domain]
            ):
                runtime_data = hass.data[domain][entry.entry_id]
                device_manager = runtime_data.manager
        else:
            runtime_data = entry.runtime_data
            device_manager = entry.runtime_data.manager
        if device_manager:
            return TuyaIntegrationRuntimeData(device_manager=device_manager, generic_runtime_data=runtime_data)
        else:
            return None
    
    def _get_overriden_tuya_integration_runtime_data(hass: HomeAssistant, entry: ConfigEntry) -> TuyaIntegrationRuntimeData | None:
        if (overriden_config_entry := MultiManager._get_overriden_config_entry(hass,entry, DOMAIN_ORIG)):
            return MultiManager._get_tuya_integration_runtime_data(hass, overriden_config_entry, DOMAIN_ORIG)
        return None


    async def get_sharing_account(self, hass: HomeAssistant, entry: XTConfigEntry) -> TuyaSharingData | None:
        #See if our current entry is an override of a Tuya integration entry
        tuya_integration_runtime_data = MultiManager._get_overriden_tuya_integration_runtime_data(hass, entry)
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
        device_manager.add_device_listener(device_listener)
        return TuyaIOTData(device_manager=device_manager,mq=mq,device_ids=device_ids,device_listener=device_listener)
    
    def update_device_cache(self):
        if self.sharing_account:
            self.sharing_account.device_manager.update_device_cache()
    
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
        if self.iot_account:
            for device_id in self.iot_account.device_manager.device_map:
                aggregated_list[device_id] = XTDevice.from_customer_device(self.iot_account.device_manager.device_map[device_id])
        if self.sharing_account:
            for device_id in self.sharing_account.device_manager.device_map:
                aggregated_list[device_id] = XTDevice.from_customer_device(self.sharing_account.device_manager.device_map[device_id])
    
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