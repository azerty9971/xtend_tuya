"""Support for Tuya Smart devices."""

from __future__ import annotations
import logging

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
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

from .util import (
    get_config_entry_runtime_data
)
from .services import (
    ServiceManager,
)

# Suppress logs from the library, it logs unneeded on error
logging.getLogger("tuya_sharing").setLevel(logging.CRITICAL)

async def update_listener(hass: HomeAssistant, entry: XTConfigEntry):
    """Handle options update."""
    hass.config_entries.async_schedule_reload(entry.entry_id)

async def async_setup_entry(hass: HomeAssistant, entry: XTConfigEntry) -> bool:
    """Async setup hass config entry.""" 
    multi_manager = MultiManager(hass)
    service_manager = ServiceManager(multi_manager=multi_manager)
    await multi_manager.setup_entry(hass, entry)

    # Get all devices from Tuya
    await hass.async_add_executor_job(multi_manager.update_device_cache)

    # Connection is successful, store the manager & listener
    entry.runtime_data = HomeAssistantXTData(multi_manager=multi_manager, listener=multi_manager.multi_device_listener, service_manager=service_manager)

    # Cleanup device registry
    await cleanup_device_registry(hass, multi_manager, entry)

    # Register known device IDs
    device_registry = dr.async_get(hass)
    aggregated_device_map = multi_manager.device_map
    for device in aggregated_device_map.values():
        domain_identifiers:list = multi_manager.get_domain_identifiers_of_device(device.id)
        identifiers: set[tuple[str, str]] = set()
        for domain_identifier in domain_identifiers:
            identifiers.add((domain_identifier, device.id))
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers=identifiers,
            manufacturer="Tuya",
            name=device.name,
            model=f"{device.product_name} (unsupported)",
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    for device in aggregated_device_map.values():
        multi_manager.virtual_state_handler.apply_init_virtual_states(device)
        
    # If the device does not register any entities, the device does not need to subscribe
    # So the subscription is here
    await hass.async_add_executor_job(multi_manager.refresh_mq)
    service_manager.register_services()
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
    config_entries: XTConfigEntry = hass.config_entries.async_entries(domain, False, False)
    for config_entry in config_entries:
        runtime_data = get_config_entry_runtime_data(hass, config_entry, domain)
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
    """Unloading the Tuya platforms."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        tuya = entry.runtime_data
        if tuya.manager.mq is not None:
            tuya.manager.mq.stop()
        tuya.manager.remove_device_listeners()
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: XTConfigEntry) -> None:
    """Remove a config entry.

    This will revoke the credentials from Tuya.
    """
    await hass.async_add_executor_job(entry.runtime_data.multi_manager.unload)