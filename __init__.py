"""Support for Tuya Smart devices."""
from __future__ import annotations

from typing import NamedTuple

import requests
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
    TuyaDeviceFunction,
    TuyaDeviceStatusRange,
)

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import (
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_APP_TYPE,
    CONF_AUTH_TYPE,
    CONF_COUNTRY_CODE,
    CONF_ENDPOINT,
    CONF_PASSWORD,
    CONF_PROJECT_TYPE,
    CONF_USERNAME,
    DOMAIN,
    DOMAIN_ORIG,
    LOGGER,
    PLATFORMS,
    TUYA_DISCOVERY_NEW,
    TUYA_HA_SIGNAL_UPDATE_ENTITY,
    DPCode,
    VirtualStates,
    DescriptionVirtualState,
)


class HomeAssistantTuyaData(NamedTuple):
    """Tuya data stored in the Home Assistant data object."""

    device_listener: TuyaDeviceListener
    device_manager: TuyaDeviceManager
    home_manager: TuyaHomeManager

from .sensor import (
    SENSORS,
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Async setup hass config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    LOGGER.debug(f"config_entry -> {vars(entry)}")

    #Prevent multiple API connection (these are automatically closed on Tuya's side ...)
    reuse_config = False
    if DOMAIN_ORIG in hass.data:
        tuya_data = hass.data[DOMAIN_ORIG]
        for config in tuya_data:
            config_entry = hass.config_entries.async_get_entry(config)
            if (
                entry.data[CONF_ENDPOINT]           == config_entry.data[CONF_ENDPOINT]
                and entry.data[CONF_ACCESS_ID]      == config_entry.data[CONF_ACCESS_ID]
                and entry.data[CONF_ACCESS_SECRET]  == config_entry.data[CONF_ACCESS_SECRET]
                and entry.data[CONF_AUTH_TYPE]      == config_entry.data[CONF_AUTH_TYPE]
                and entry.data[CONF_USERNAME]       == config_entry.data[CONF_USERNAME]
                and entry.data[CONF_PASSWORD]       == config_entry.data[CONF_PASSWORD]
                and entry.data[CONF_COUNTRY_CODE]   == config_entry.data[CONF_COUNTRY_CODE]
                and entry.data[CONF_APP_TYPE]       == config_entry.data[CONF_APP_TYPE]
            ):
                orig_config = hass.data[DOMAIN_ORIG][config]
                tuya_device_manager = orig_config.device_manager
                api = tuya_device_manager.api
                tuya_mq = tuya_device_manager.mq
                reuse_config = True
                break
    
    if reuse_config == False:
        # Project type has been renamed to auth type in the upstream Tuya IoT SDK.
        # This migrates existing config entries to reflect that name change.
        if CONF_PROJECT_TYPE in entry.data:
            data = {**entry.data, CONF_AUTH_TYPE: entry.data[CONF_PROJECT_TYPE]}
            data.pop(CONF_PROJECT_TYPE)
            hass.config_entries.async_update_entry(entry, data=data)

        auth_type = AuthType(entry.data[CONF_AUTH_TYPE])
        api = TuyaOpenAPI(
            endpoint=entry.data[CONF_ENDPOINT],
            access_id=entry.data[CONF_ACCESS_ID],
            access_secret=entry.data[CONF_ACCESS_SECRET],
            auth_type=auth_type,
        )

        api.set_dev_channel("hass")

        try:
            if auth_type == AuthType.CUSTOM:
                response = await hass.async_add_executor_job(
                    api.connect, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
                )
            else:
                response = await hass.async_add_executor_job(
                    api.connect,
                    entry.data[CONF_USERNAME],
                    entry.data[CONF_PASSWORD],
                    entry.data[CONF_COUNTRY_CODE],
                    entry.data[CONF_APP_TYPE],
                )
        except requests.exceptions.RequestException as err:
            raise ConfigEntryNotReady(err) from err

        if response.get("success", False) is False:
            raise ConfigEntryNotReady(response)

        tuya_mq = TuyaOpenMQ(api)
        tuya_mq.start()

    device_ids: set[str] = set()
    device_manager = DeviceManager(api, tuya_mq)
    home_manager = TuyaHomeManager(api, tuya_mq, device_manager)
    listener = DeviceListener(hass, device_manager, device_ids)
    LOGGER.debug(f"MQ status before -> {tuya_mq.message_listeners}")
    if reuse_config == True:
        # Remove the original message queue listener because otherwise we could have a race condition where the modified state
        # is overwritten by the original code
        tuya_device_manager.remove_device_listener(orig_config.device_listener)
        tuya_mq.remove_message_listener(tuya_device_manager.on_message)
        device_manager.set_overriden_device_manager(tuya_device_manager)
    device_manager.add_device_listener(listener)
    LOGGER.debug(f"MQ status after -> {tuya_mq.message_listeners}")

    hass.data[DOMAIN][entry.entry_id] = HomeAssistantTuyaData(
        device_listener=listener,
        device_manager=device_manager,
        home_manager=home_manager,
    )

    # Get devices & clean up device entities
    await hass.async_add_executor_job(home_manager.update_device_cache)
    await cleanup_device_registry(hass, device_manager)

    # Migrate old unique_ids to the new format
    async_migrate_entities_unique_ids(hass, entry, device_manager)

    # Register known device IDs
    device_registry = dr.async_get(hass)
    for device in device_manager.device_map.values():
        if registered_device := device_registry.async_get_device(
            identifiers={(DOMAIN_ORIG, device.id)}
        ):
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN_ORIG, device.id), (DOMAIN, device.id)},
                manufacturer="Tuya",
                name=device.name,
                model=registered_device.model,
            )
            device_ids.add(device.id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def cleanup_device_registry(
    hass: HomeAssistant, device_manager: TuyaDeviceManager
) -> None:
    """Remove deleted device registry entry if there are no remaining entities."""
    device_registry = dr.async_get(hass)
    for dev_id, device_entry in list(device_registry.devices.items()):
        for item in device_entry.identifiers:
            if item[0] == DOMAIN and item[1] not in device_manager.device_map:
                device_registry.async_remove_device(dev_id)
                break


@callback
def async_migrate_entities_unique_ids(
    hass: HomeAssistant, config_entry: ConfigEntry, device_manager: TuyaDeviceManager
) -> None:
    """Migrate unique_ids in the entity registry to the new format."""
    pass


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unloading the Tuya platforms."""
    unload = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload:
        hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]
        hass_data.device_manager.mq.stop()
        hass_data.device_manager.remove_device_listener(hass_data.device_listener)

        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload




class DeviceManager(TuyaDeviceManager):
    def __init__(
        self,
        api: TuyaOpenAPI, 
        mq: TuyaOpenMQ
    ) -> None:
        super().__init__(api, mq)
        self.other_device_manager = None
    
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
    
    def set_overriden_device_manager(self, other_device_manager: TuyaDeviceManager) -> None:
        self.other_device_manager = other_device_manager

    def on_message(self, msg: str):
        #If we override another device manager, first call its on_message method
        if self.other_device_manager is not None:
            self.other_device_manager.on_message(msg)
        super().on_message(msg)

    def _on_device_report(self, device_id: str, status: list):
        device = self.device_map.get(device_id, None)
        if not device:
            return

        virtual_states = DeviceManager.get_category_virtual_states(device.category)
        show_debug = False
        
        for virtual_state in virtual_states:
            if virtual_state.virtual_state_value == VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD:
                if virtual_state.key not in device.status or device.status[virtual_state.key] is None:
                    device.status[virtual_state.key] = 0
                if virtual_state.key in device.status:
                    for item in status:
                        if "code" in item and "value" in item and item["code"] == virtual_state.key:
                            #if show_debug == False:
                            #    LOGGER.debug(f"BEFORE device_id -> {device_id} device_status-> {device.status} status-> {status} VS-> {virtual_states}")
                            #    show_debug = True
                            item["value"] += device.status[virtual_state.key]
                            item_val = item["value"]
                            #LOGGER.debug(f"Applying virtual state device_id -> {device_id} device_status-> {device.status[virtual_state.key]} status-> {item_val} VS-> {virtual_state}")
                        

        for item in status:
            if "code" in item and "value" in item and item["value"] is not None:
                code = item["code"]
                value = item["value"]
                device.status[code] = value
        if self.other_device_manager is not None:
            device_other = self.other_device_manager.device_map.get(device_id, None)
            if not device:
                return
            for item in status:
                if "code" in item and "value" in item and item["value"] is not None:
                    code = item["code"]
                    value = item["value"]
                    device_other.status[code] = value
        #if show_debug == True:
        #    LOGGER.debug(f"AFTER device_id -> {device_id} device_status-> {device.status} status-> {status}")
        super()._on_device_report(device_id, [])

class DeviceListener(TuyaDeviceListener):
    """Device Update Listener."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_manager: TuyaDeviceManager,
        device_ids: set[str],
    ) -> None:
        """Init DeviceListener."""
        self.hass = hass
        self.device_manager = device_manager
        self.device_ids = device_ids

    def update_device(self, device: TuyaDevice) -> None:
        """Update device status."""
        if device.id in self.device_ids:
            dispatcher_send(self.hass, f"{TUYA_HA_SIGNAL_UPDATE_ENTITY}_{device.id}")

    def add_device(self, device: TuyaDevice) -> None:
        """Add device added listener."""
        # Ensure the device isn't present stale
        self.hass.add_job(self.async_remove_device, device.id)

        self.device_ids.add(device.id)
        dispatcher_send(self.hass, TUYA_DISCOVERY_NEW, [device.id])

        device_manager = self.device_manager
        device_manager.mq.stop()
        tuya_mq = TuyaOpenMQ(device_manager.api)
        tuya_mq.start()

        device_manager.mq = tuya_mq
        tuya_mq.add_message_listener(device_manager.on_message)

    def remove_device(self, device_id: str) -> None:
        """Add device removed listener."""
        self.hass.add_job(self.async_remove_device, device_id)

    @callback
    def async_remove_device(self, device_id: str) -> None:
        """Remove device from Home Assistant."""
        LOGGER.debug("Remove device: %s", device_id)
        device_registry = dr.async_get(self.hass)
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, device_id)}
        )
        if device_entry is not None:
            device_registry.async_remove_device(device_entry.id)
            self.device_ids.discard(device_id)
