"""Support for Tuya Smart devices."""

from __future__ import annotations
import logging

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import (
    DOMAIN,
    DOMAIN_ORIG,
    PLATFORMS,
)

from .multi_manager.multi_manager import (
    MultiManager,
    XTConfigEntry,
)

from .multi_manager.shared.shared_classes import (
    HomeAssistantXTData,
)

from .multi_manager.tuya_sharing.ha_tuya_integration.tuya_decorators import (
    decorate_tuya_integration
)

from .util import (
    get_tuya_integration_runtime_data
)

# Suppress logs from the library, it logs unneeded on error
logging.getLogger("tuya_sharing").setLevel(logging.CRITICAL)

async def update_listener(hass, entry):
    """Handle options update."""
    hass.config_entries.async_schedule_reload(entry.entry_id)

async def async_setup_entry(hass: HomeAssistant, entry: XTConfigEntry) -> bool:
    #LOGGER.warning(f"async_setup_entry {entry.title} : {entry.data}")
    """Async setup hass config entry.""" 
    multi_manager = MultiManager(hass)
    await multi_manager.setup_entry(hass, entry)
    if multi_manager.sharing_account and multi_manager.sharing_account.ha_tuya_integration_config_manager:
        decorate_tuya_integration(multi_manager.sharing_account.ha_tuya_integration_config_manager)

    # Get all devices from Tuya
    try:
        await hass.async_add_executor_job(multi_manager.update_device_cache)
    except Exception as exc:
        # While in general, we should avoid catching broad exceptions,
        # we have no other way of detecting this case.
        if "sign invalid" in str(exc):
            msg = "Authentication failed. Please re-authenticate the Tuya integration"
            if multi_manager.sharing_account and multi_manager.sharing_account.reuse_config:
                raise ConfigEntryNotReady(msg) from exc
            else:
                raise ConfigEntryAuthFailed("Authentication failed. Please re-authenticate.")
        raise

    # Connection is successful, store the manager & listener
    entry.runtime_data = HomeAssistantXTData(multi_manager=multi_manager, listener=multi_manager.multi_device_listener)

    # Cleanup device registry
    await cleanup_device_registry(hass, multi_manager, entry)

    # Register known device IDs
    device_registry = dr.async_get(hass)
    aggregated_device_map = multi_manager.device_map
    for device in aggregated_device_map.values():
        if ( 
            multi_manager.sharing_account
            and multi_manager.sharing_account.reuse_config
            and device_registry.async_get_device(identifiers={(DOMAIN_ORIG, device.id)}, connections=None)
        ):
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

    for device in aggregated_device_map.values():
        multi_manager.apply_init_virtual_states(device)
        multi_manager.allow_virtual_devices_not_set_up(device)
    # If the device does not register any entities, the device does not need to subscribe
    # So the subscription is here
    await hass.async_add_executor_job(multi_manager.refresh_mq)
    return True


async def cleanup_device_registry(hass: HomeAssistant, multi_manager: MultiManager, current_entry: ConfigEntry) -> None:
    """Remove deleted device registry entry if there are no remaining entities."""
    if not are_all_domain_config_loaded(hass, DOMAIN, current_entry):
        return
    if not are_all_domain_config_loaded(hass, DOMAIN_ORIG, current_entry):
        return
    device_registry = dr.async_get(hass)
    for dev_id, device_entry in list(device_registry.devices.items()):
        for item in device_entry.identifiers:
            if not is_device_in_domain_device_maps(hass, [DOMAIN_ORIG, DOMAIN],item):
                device_registry.async_remove_device(dev_id)
                break

def are_all_domain_config_loaded(hass: HomeAssistant, domain: str, current_entry: ConfigEntry) -> bool:
    config_entries = hass.config_entries.async_entries(domain, False, False)
    for config_entry in config_entries:
        if config_entry.entry_id == current_entry.entry_id:
            continue
        if config_entry.state is not ConfigEntryState.LOADED:
            return False
    return True

def get_domain_device_map(hass: HomeAssistant, domain: str) -> dict[str, any]:
    device_map = {}
    config_entries = hass.config_entries.async_entries(domain, False, False)
    for config_entry in config_entries:
        runtime_data = get_tuya_integration_runtime_data(hass, config_entry, domain)
        for device_id in runtime_data.device_manager.device_map:
            if device_id not in device_map:
                device_map[device_id] = runtime_data.device_manager.device_map[device_id]
    return device_map

def is_device_in_domain_device_maps(hass: HomeAssistant, domains: list[str], device_entry_identifiers: list[str]):
    device_id = device_entry_identifiers[1]
    device_domain = device_entry_identifiers[0]
    if device_domain in domains:
        for domain in domains:
            device_map = get_domain_device_map(hass, domain)
            if device_id in device_map:
                return True
    else:
        return True
    
    return False

async def async_unload_entry(hass: HomeAssistant, entry: XTConfigEntry) -> bool:
    #LOGGER.warning(f"async_unload_entry {entry.title} : {entry.data}")
    """Unloading the Tuya platforms."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        tuya = entry.runtime_data
        if tuya.manager.mq is not None:
            tuya.manager.mq.stop()
        tuya.manager.remove_device_listeners()
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: XTConfigEntry) -> None:
    #LOGGER.warning(f"async_remove_entry {entry.title} : {entry.data}")
    """Remove a config entry.

    This will revoke the credentials from Tuya.
    """
    if not entry.multi_manager.sharing_account or not entry.multi_manager.sharing_account.reuse_config:
        multi_manager = entry.multi_manager
        await hass.async_add_executor_job(multi_manager.unload)