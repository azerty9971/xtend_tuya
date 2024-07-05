"""Support for Tuya Smart devices."""

from __future__ import annotations

import logging
from typing import Any, NamedTuple

from tuya_sharing.manager import (
    Manager,
    SharingDeviceListener,
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
from tuya_sharing.device import (
    CustomerDevice,
    DeviceRepository,
    DeviceFunction,
    DeviceStatusRange,
)
from tuya_sharing.scenes import (
    SceneRepository,
)
from tuya_sharing.user import (
    UserRepository,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import (
    CONF_APP_TYPE,
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
)

# Suppress logs from the library, it logs unneeded on error
logging.getLogger("tuya_sharing").setLevel(logging.CRITICAL)

type TuyaConfigEntry = ConfigEntry[HomeAssistantTuyaData]


class HomeAssistantTuyaData(NamedTuple):
    """Tuya data stored in the Home Assistant data object."""

    manager: Manager
    listener: SharingDeviceListener
    reuse_config: bool = False

from .sensor import (
    SENSORS,
)

async def update_listener(hass, entry):
    """Handle options update."""
    pass

async def async_setup_entry(hass: HomeAssistant, entry: TuyaConfigEntry) -> bool:
    """Async setup hass config entry."""
    entry.async_on_unload(entry.add_update_listener(update_listener))
    reuse_config = False
    tuya_data = hass.config_entries.async_entries(DOMAIN_ORIG,False,False)
    for config_entry in tuya_data:
        if entry.title == config_entry.title:
            reuse_config = True
            if (
                not hasattr(config_entry, 'runtime_data') 
                or config_entry.runtime_data is None 
                or hasattr(config_entry.runtime_data, 'tainted')
            ):
                #Try to fetch the manager using the old way
                tuya_device_manager = None
                if ( DOMAIN_ORIG in hass.data and
                    config_entry.entry_id in hass.data[DOMAIN_ORIG]
                ):
                    orig_config = hass.data[DOMAIN_ORIG][config_entry.entry_id]
                    tuya_device_manager = orig_config.manager
                if tuya_device_manager is None:
                    msg = "Authentication failed. Please re-authenticate the Tuya integration"
                    raise ConfigEntryError(msg)
            else:
                tuya_device_manager = config_entry.runtime_data.manager
            
            manager = DeviceManager(
                TUYA_CLIENT_ID,
                config_entry.data[CONF_USER_CODE],
                config_entry.data[CONF_TERMINAL_ID],
                config_entry.data[CONF_ENDPOINT],
                config_entry.data[CONF_TOKEN_INFO],
                None,
                tuya_device_manager
            )
            break
    
    if not reuse_config:
        token_listener = TokenListener(hass, entry)
        manager = DeviceManager(
            TUYA_CLIENT_ID,
            entry.data[CONF_USER_CODE],
            entry.data[CONF_TERMINAL_ID],
            entry.data[CONF_ENDPOINT],
            entry.data[CONF_TOKEN_INFO],
            token_listener,
        )

    listener = DeviceListener(hass, manager)
    manager.add_device_listener(listener)

    # Get all devices from Tuya
    try:
        await hass.async_add_executor_job(manager.update_device_cache)
    except Exception as exc:
        # While in general, we should avoid catching broad exceptions,
        # we have no other way of detecting this case.
        if "sign invalid" in str(exc):
            msg = "Authentication failed. Please re-authenticate the Tuya integration"
            if reuse_config:
                setattr(config_entry.runtime_data, 'tainted', True)
                raise ConfigEntryError(msg) from exc
            else:
                raise ConfigEntryAuthFailed("Authentication failed. Please re-authenticate.")
        raise

    # Connection is successful, store the manager & listener
    entry.runtime_data = HomeAssistantTuyaData(manager=manager, listener=listener, reuse_config=reuse_config)

    # Cleanup device registry
    await cleanup_device_registry(hass, manager)

    # Register known device IDs
    device_registry = dr.async_get(hass)
    for device in manager.device_map.values():
        if reuse_config:
            identifiers = {(DOMAIN_ORIG, device.id), (DOMAIN, device.id)}
        else:
            identifiers = {(DOMAIN, device.id)}
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers=identifiers,
            manufacturer="Tuya",
            name=device.name,
            model=f"{device.product_name} (unsupported)",
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # If the device does not register any entities, the device does not need to subscribe
    # So the subscription is here
    await hass.async_add_executor_job(manager.refresh_mq)
    return True


async def cleanup_device_registry(hass: HomeAssistant, device_manager: Manager) -> None:
    """Remove deleted device registry entry if there are no remaining entities."""
    device_registry = dr.async_get(hass)
    for dev_id, device_entry in list(device_registry.devices.items()):
        for item in device_entry.identifiers:
            if item[0] == DOMAIN and item[1] not in device_manager.device_map:
                device_registry.async_remove_device(dev_id)
                break


async def async_unload_entry(hass: HomeAssistant, entry: TuyaConfigEntry) -> bool:
    """Unloading the Tuya platforms."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        tuya = entry.runtime_data
        if tuya.manager.mq is not None and tuya.manager.get_overriden_device_manager() is not None:
            tuya.manager.mq.stop()
        tuya.manager.remove_device_listener(tuya.listener)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: TuyaConfigEntry) -> None:
    """Remove a config entry.

    This will revoke the credentials from Tuya.
    """
    if not entry.reuse_config:
        manager = Manager(
            TUYA_CLIENT_ID,
            entry.data[CONF_USER_CODE],
            entry.data[CONF_TERMINAL_ID],
            entry.data[CONF_ENDPOINT],
            entry.data[CONF_TOKEN_INFO],
        )
        await hass.async_add_executor_job(manager.unload)


class DeviceListener(SharingDeviceListener):
    """Device Update Listener."""

    def __init__(
        self,
        hass: HomeAssistant,
        manager: Manager,
    ) -> None:
        """Init DeviceListener."""
        self.hass = hass
        self.manager = manager

    def update_device(self, device: CustomerDevice) -> None:
        """Update device status."""
        #LOGGER.debug(
        #    "Received update for device %s: %s",
        #    device.id,
        #    self.manager.device_map[device.id].status,
        #)
        dispatcher_send(self.hass, f"{TUYA_HA_SIGNAL_UPDATE_ENTITY}_{device.id}")

    def add_device(self, device: CustomerDevice) -> None:
        """Add device added listener."""
        # Ensure the device isn't present stale
        self.hass.add_job(self.async_remove_device, device.id)

        dispatcher_send(self.hass, TUYA_DISCOVERY_NEW, [device.id])

    def remove_device(self, device_id: str) -> None:
        """Add device removed listener."""
        self.hass.add_job(self.async_remove_device, device_id)

    @callback
    def async_remove_device(self, device_id: str) -> None:
        """Remove device from Home Assistant."""
        #LOGGER.debug("Remove device: %s", device_id)
        device_registry = dr.async_get(self.hass)
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, device_id)}
        )
        if device_entry is not None:
            device_registry.async_remove_device(device_entry.id)


class TokenListener(SharingTokenListener):
    """Token listener for upstream token updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TuyaConfigEntry,
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

class XTDeviceRepository(DeviceRepository):
    def __init__(self, customer_api: CustomerApi, manager: DeviceManager):
        super().__init__(customer_api)
        self.manager = manager

    def update_device_specification(self, device: CustomerDevice):
        device_id = device.id
        response = self.api.get(f"/v1.1/m/life/{device_id}/specifications")
        LOGGER.warning(f"update_device_specification => {response}")
        if response.get("success"):
            result = response.get("result", {})
            function_map = {}
            for function in result["functions"]:
                code = function["code"]
                function_map[code] = DeviceFunction(**function)

            status_range = {}
            for status in result["status"]:
                code = status["code"]
                status_range[code] = DeviceStatusRange(**status)

            device.function = function_map
            device.status_range = status_range

    def update_device_strategy_info(self, device: CustomerDevice):
        device_id = device.id
        response = self.api.get(f"/v1.0/m/life/devices/{device_id}/status")
        LOGGER.warning(f"update_device_strategy_info => {response}")
        support_local = True
        if response.get("success"):
            result = response.get("result", {})
            pid = result["productKey"]
            dp_id_map = {}
            tuya_device = None
            tuya_manager = self.manager.get_overriden_device_manager()
            if tuya_manager is None:
                tuya_manager = self.manager
            if device.id in tuya_manager.device_map:
                tuya_device = tuya_manager.device_map[device.id]
            for dp_status_relation in result["dpStatusRelationDTOS"]:
                if not dp_status_relation["supportLocal"]:
                    support_local = False
                else:
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
                if "statusCode" in dp_status_relation:
                    code = dp_status_relation["statusCode"]
                    if code not in device.status_range:
                        device.status_range[code] = DeviceStatusRange()
                        device.status_range[code].code   = code
                        device.status_range[code].type   = dp_status_relation["valueType"]
                        device.status_range[code].values = dp_status_relation["valueDesc"]
                    #Also add the status range for Tuya's manager devices
                    if tuya_device is not None and code not in tuya_device.status_range:
                        tuya_device.status_range[code] = DeviceStatusRange()
                        tuya_device.status_range[code].code   = code
                        tuya_device.status_range[code].type   = dp_status_relation["valueType"]
                        tuya_device.status_range[code].values = dp_status_relation["valueDesc"]
            device.support_local = support_local
            if support_local:
                device.local_strategy = dp_id_map

class DeviceManager(Manager):
    def __init__(
        self,
        client_id: str,
        user_code: str,
        terminal_id: str,
        end_point: str,
        token_response: dict[str, Any] = None,
        listener: SharingTokenListener = None,
        other_manager: Manager = None,
    ) -> None:
        if other_manager is None:
            self.terminal_id = terminal_id
            self.customer_api = CustomerApi(
                CustomerTokenInfo(token_response),
                client_id,
                user_code,
                end_point,
                listener,
            )
            self.mq = None
        else:
            self.terminal_id = other_manager.terminal_id
            self.customer_api = other_manager.customer_api
            #LOGGER.warning(f"self.customer_api => {self.customer_api}")
            self.mq = other_manager.mq
            if self.mq is not None and self.mq.mq_config is not None:
                LOGGER.warning(f"MQTT config: URL => {self.mq.mq_config.url} ClientID => {self.mq.mq_config.client_id} Username => {self.mq.mq_config.username} Password => {self.mq.mq_config.password} Dev Topic => {self.mq.mq_config.dev_topic}")
            self.mq.remove_message_listener(other_manager.on_message)
        self.other_device_manager = other_manager
        self.device_map: dict[str, CustomerDevice] = {}
        self.user_homes: list[SmartLifeHome] = []
        self.home_repository = HomeRepository(self.customer_api)
        self.device_repository = XTDeviceRepository(self.customer_api, self)
        self.device_listeners = set()
        self.scene_repository = SceneRepository(self.customer_api)
        self.user_repository = UserRepository(self.customer_api)
    
    @staticmethod
    def get_category_virtual_states(category: str) -> list[DescriptionVirtualState]:
        to_return = []
        for virtual_state in VirtualStates:
            if (descriptions := SENSORS.get(category)):
                for description in descriptions:
                    if description.virtualstate is not None and description.virtualstate & virtual_state.value:
                        # This VirtualState is applied to this key, let's return it
                        found_virtual_state = DescriptionVirtualState(description.key, virtual_state.name, virtual_state.value)
                        to_return.append(found_virtual_state)
        return to_return
    
    def set_overriden_device_manager(self, other_device_manager: Manager) -> None:
        self.other_device_manager = other_device_manager
    
    def get_overriden_device_manager(self) -> Manager | None:
        if self.other_device_manager is not None:
            return self.other_device_manager
        return None

    def on_message(self, msg: str):
        #If we override another device manager, first call its on_message method
        if self.other_device_manager is not None:
            self.other_device_manager.on_message(msg)
        super().on_message(msg)

    def refresh_mq(self):
        if self.other_device_manager is not None:
            self.mq = self.other_device_manager.mq
            self.mq.add_message_listener(self.on_message)
            return
        super().refresh_mq()

    def _on_device_other(self, device_id: str, biz_code: str, data: dict[str, Any]):
        #LOGGER.warning(f"mq _on_device_other-> {device_id} biz_code-> {biz_code} data-> {data}")
        super()._on_device_other(device_id, biz_code, data)

    def _on_device_report(self, device_id: str, status: list):
        device = self.device_map.get(device_id, None)
        #LOGGER.debug(f"mq _on_device_report-> {device_id} status-> {status}")
        if not device:
            return
        #LOGGER.debug(f"Device found!")
        virtual_states = DeviceManager.get_category_virtual_states(device.category)
        #show_debug = False
        
        #LOGGER.debug(f"Found virtualstates -> {virtual_states}")
        for virtual_state in virtual_states:
            if virtual_state.virtual_state_value == VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD:
                if virtual_state.key not in device.status or device.status[virtual_state.key] is None:
                    device.status[virtual_state.key] = 0
                if virtual_state.key in device.status:
                    for item in status:
                        if "code" in item and "value" in item and item["code"] == virtual_state.key:
                            #LOGGER.debug(f"BEFORE device_id -> {device_id} device_status-> {device.status} status-> {status} VS-> {virtual_states}")
                            item["value"] += device.status[virtual_state.key]
                            #item_val = item["value"]
                            #LOGGER.debug(f"Applying virtual state device_id -> {device_id} device_status-> {device.status[virtual_state.key]} status-> {item_val} VS-> {virtual_state}")
                        elif "dpId" in item and "value" in item:
                            dp_id_item = device.local_strategy[item["dpId"]]
                            #LOGGER.debug(f"device local strategy -> {device.local_strategy}, dp_id_item -> {dp_id_item} device_status-> {device.status}")
                            code = dp_id_item["status_code"]
                            value = item["value"]
                            if code == virtual_state.key:
                                #LOGGER.debug(f"dpId logic before -> {device_id} device_status-> {device.status} status-> {status}")
                                item["value"] += device.status[virtual_state.key]
                                #LOGGER.debug(f"dpId logic after -> {device_id} device_status-> {device.status} status-> {status}")
                        
        #LOGGER.debug(f"Next step")
        for item in status:
            if "code" in item and "value" in item and item["value"] is not None:
                code = item["code"]
                value = item["value"]
                device.status[code] = value
            elif "dpId" in item and "value" in item:
                dp_id_item = device.local_strategy[item["dpId"]]
                code = dp_id_item["status_code"]
                value = item["value"]
                device.status[code] = value
        if self.other_device_manager is not None:
            device_other = self.other_device_manager.device_map.get(device_id, None)
            if device:
                for item in status:
                    if "code" in item and "value" in item and item["value"] is not None:
                        code = item["code"]
                        value = item["value"]
                        device_other.status[code] = value
                    elif "dpId" in item and "value" in item:
                        dp_id_item = device.local_strategy[item["dpId"]]
                        code = dp_id_item["status_code"]
                        value = item["value"]
                        device_other.status[code] = value
        
        #if show_debug == True:
        #LOGGER.debug(f"AFTER device_id -> {device_id} device_status-> {device.status} status-> {status}")
        super()._on_device_report(device_id, [])