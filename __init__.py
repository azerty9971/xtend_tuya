"""Support for Tuya Smart devices."""

from __future__ import annotations

import logging
from typing import Any, NamedTuple

from tuya_sharing import (
    CustomerDevice,
    Manager,
    SharingDeviceListener,
    SharingTokenListener,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
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


class HomeAssistantTuyaData(NamedTuple):
    """Tuya data stored in the Home Assistant data object."""

    manager: Manager
    listener: SharingDeviceListener

from .sensor import (
    SENSORS,
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Async setup hass config entry."""
    if CONF_APP_TYPE in entry.data:
        raise ConfigEntryAuthFailed("Authentication failed. Please re-authenticate.")

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

    #reuse_config = False
    if DOMAIN_ORIG in hass.data:
        tuya_data = hass.data[DOMAIN_ORIG]
        for config in tuya_data:
            config_entry = hass.config_entries.async_get_entry(config)
            if (
                    entry.data[CONF_USER_CODE]      == config_entry.data[CONF_USER_CODE]
                and entry.data[CONF_TERMINAL_ID]    == config_entry.data[CONF_TERMINAL_ID]
                and entry.data[CONF_ENDPOINT]       == config_entry.data[CONF_ENDPOINT]
                and entry.data[CONF_TOKEN_INFO]     == config_entry.data[CONF_TOKEN_INFO]
            ):
                orig_config = hass.data[DOMAIN_ORIG][config]
                tuya_device_manager = orig_config.manager
                tuya_mq = tuya_device_manager.mq
                manager.set_overriden_device_manager(tuya_device_manager)
                tuya_device_manager.remove_device_listener(orig_config.listener)
                tuya_mq.remove_message_listener(tuya_device_manager.on_message)
                break

    # Get all devices from Tuya
    try:
        await hass.async_add_executor_job(manager.update_device_cache)
    except Exception as exc:
        # While in general, we should avoid catching broad exceptions,
        # we have no other way of detecting this case.
        if "sign invalid" in str(exc):
            msg = "Authentication failed. Please re-authenticate"
            raise ConfigEntryAuthFailed(msg) from exc
        raise

    # Connection is successful, store the manager & listener
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = HomeAssistantTuyaData(
        manager=manager, listener=listener
    )

    # Cleanup device registry
    await cleanup_device_registry(hass, manager)

    # Register known device IDs
    device_registry = dr.async_get(hass)
    for device in manager.device_map.values():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN_ORIG, device.id), (DOMAIN, device.id)},
            manufacturer="Tuya",
            name=device.name,
            model=f"{device.product_name}",
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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unloading the Tuya platforms."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        tuya: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]
        if tuya.manager.mq is not None:
            tuya.manager.mq.stop()
        tuya.manager.remove_device_listener(tuya.listener)
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry.

    This will revoke the credentials from Tuya.
    """
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
        LOGGER.debug(
            "Received update for device %s: %s",
            device.id,
            self.manager.device_map[device.id].status,
        )
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
        LOGGER.debug("Remove device: %s", device_id)
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
        entry: ConfigEntry,
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


class DeviceManager(Manager):
    def __init__(
        self,
        client_id: str,
        user_code: str,
        terminal_id: str,
        end_point: str,
        token_response: dict[str, Any] = None,
        listener: SharingTokenListener = None,
    ) -> None:
        super().__init__(client_id, user_code, terminal_id, end_point, token_response, listener)
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
    
    def set_overriden_device_manager(self, other_device_manager: Manager) -> None:
        self.other_device_manager = other_device_manager

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


    def _on_device_report(self, device_id: str, status: list):
        device = self.device_map.get(device_id, None)
        if not device:
            return

        virtual_states = DeviceManager.get_category_virtual_states(device.category)
        #show_debug = False
        
        for virtual_state in virtual_states:
            if virtual_state.virtual_state_value == VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD:
                if virtual_state.key not in device.status or device.status[virtual_state.key] is None:
                    device.status[virtual_state.key] = 0
                if virtual_state.key in device.status:
                    for item in status:
                        if "code" in item and "value" in item and item["code"] == virtual_state.key:
                            #if show_debug == False:
                            LOGGER.debug(f"BEFORE device_id -> {device_id} device_status-> {device.status} status-> {status} VS-> {virtual_states}")
                            #    show_debug = True
                            item["value"] += device.status[virtual_state.key]
                            item_val = item["value"]
                            LOGGER.debug(f"Applying virtual state device_id -> {device_id} device_status-> {device.status[virtual_state.key]} status-> {item_val} VS-> {virtual_state}")
                        if "dpId" in item and "value" in item:
                            dp_id_item = device.local_strategy[item["dpId"]]
                            strategy_name = dp_id_item["value_convert"]
                            config_item = dp_id_item["config_item"]
                            dp_item = (dp_id_item["status_code"], item["value"])
                            code, value = strategy.convert(strategy_name, dp_item, config_item)
                            if code == virtual_state.key:
                                LOGGER.debug(f"dpId logic before -> {device_id} device_status-> {device.status} status-> {status}")
                                device.status[code] += value
                                LOGGER.debug(f"dpId logic after -> {device_id} device_status-> {device.status} status-> {status}")
                        

        for item in status:
            if "code" in item and "value" in item and item["value"] is not None:
                code = item["code"]
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
        #if show_debug == True:
        LOGGER.debug(f"AFTER device_id -> {device_id} device_status-> {device.status} status-> {status}")
        super()._on_device_report(device_id, [])