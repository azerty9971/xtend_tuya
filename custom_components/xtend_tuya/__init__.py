"""Support for Tuya Smart devices."""

from __future__ import annotations

import logging
import json
import copy
from typing import NamedTuple

import requests



from tuya_iot.device import (
    PROTOCOL_DEVICE_REPORT,
    PROTOCOL_OTHER,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import dispatcher_send

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

from .multi_manager import (
    MultiManager,
    XTConfigEntry,
    HomeAssistantXTData,
)

# Suppress logs from the library, it logs unneeded on error
logging.getLogger("tuya_sharing").setLevel(logging.CRITICAL)

async def update_listener(hass, entry):
    """Handle options update."""
    LOGGER.warning(f"update_listener => {entry}")
    LOGGER.warning(f"update_listener => {entry.data}")

async def async_setup_entry(hass: HomeAssistant, entry: XTConfigEntry) -> bool:
    """Async setup hass config entry.""" 
    LOGGER.warning("async_setup_entry")
    multi_manager = MultiManager(hass, entry)
    await multi_manager.setup_entry(hass, entry)

    # Get all devices from Tuya
    try:
        await hass.async_add_executor_job(multi_manager.update_device_cache)
    except Exception as exc:
        # While in general, we should avoid catching broad exceptions,
        # we have no other way of detecting this case.
        if "sign invalid" in str(exc):
            msg = "Authentication failed. Please re-authenticate the Tuya integration"
            if multi_manager.reuse_config:
                raise ConfigEntryNotReady(msg) from exc
            else:
                raise ConfigEntryAuthFailed("Authentication failed. Please re-authenticate.")
        raise

    # Connection is successful, store the manager & listener
    entry.runtime_data = HomeAssistantXTData(multi_manager=multi_manager, reuse_config=multi_manager.reuse_config)

    # Cleanup device registry
    await cleanup_device_registry(hass, multi_manager)

    # Register known device IDs
    device_registry = dr.async_get(hass)
    aggregated_device_map = multi_manager.get_aggregated_device_map()
    for device in aggregated_device_map.values():
        if multi_manager.reuse_config:
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
    for device in aggregated_device_map.values():
        multi_manager.apply_init_virtual_states(device)
        multi_manager.allow_virtual_devices_not_set_up(device)
    await hass.async_add_executor_job(multi_manager.refresh_mq)
    return True


async def cleanup_device_registry(hass: HomeAssistant, multi_manager: MultiManager) -> None:
    """Remove deleted device registry entry if there are no remaining entities."""
    LOGGER.warning("cleanup_device_registry")
    device_registry = dr.async_get(hass)
    for dev_id, device_entry in list(device_registry.devices.items()):
        for item in device_entry.identifiers:
            if not multi_manager.is_device_in_domain_device_maps([DOMAIN_ORIG, DOMAIN],item):
                device_registry.async_remove_device(dev_id)
                break


async def async_unload_entry(hass: HomeAssistant, entry: XTConfigEntry) -> bool:
    """Unloading the Tuya platforms."""
    LOGGER.warning("async_unload_entry")
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        tuya = entry.runtime_data
        if tuya.manager.mq is not None:
            tuya.manager.mq.stop()
        tuya.manager.remove_device_listeners()
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: XTConfigEntry) -> None:
    LOGGER.warning("async_remove_entry")
    """Remove a config entry.

    This will revoke the credentials from Tuya.
    """
    if not entry.reuse_config:
        multi_manager = entry.multi_manager
        await hass.async_add_executor_job(multi_manager.unload)