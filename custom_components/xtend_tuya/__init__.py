"""Support for Tuya Smart devices."""

from __future__ import annotations
import logging
import asyncio
from datetime import datetime
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from .const import (
    DOMAIN,
    DOMAIN_ORIG,
    PLATFORMS,
    LOGGER,
)
from .multi_manager.multi_manager import (
    MultiManager,
    XTConfigEntry,
)
from .multi_manager.shared.shared_classes import (
    HomeAssistantXTData,
)
from .multi_manager.shared.threading import (
    XTEventLoopProtector,
    XTConcurrencyManager,
)
from .util import get_config_entry_runtime_data, is_device_in_domain_device_maps
from .multi_manager.shared.services.services import (
    ServiceManager,
)
from .entity import (
    XTEntity,
)
from .models import (
    XTTuyaModelPatcher,
)

# Suppress logs from the library, it logs unneeded on error
logging.getLogger("tuya_sharing").setLevel(logging.CRITICAL)


async def update_listener(hass: HomeAssistant, entry: XTConfigEntry):
    """Handle options update."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


# async def async_setup_entry(hass: HomeAssistant, entry: XTConfigEntry) -> bool:
# return await profile_async_method(async_setup_entry2(hass=hass, entry=entry))


async def async_setup_entry(hass: HomeAssistant, entry: XTConfigEntry) -> bool:
    """Async setup hass config entry."""
    XTEventLoopProtector.hass = hass
    XTConcurrencyManager.hass = hass
    XTTuyaModelPatcher.patch_tuya_models()
    start_time = datetime.now()
    last_time = start_time
    multi_manager = MultiManager(hass, entry)
    service_manager = ServiceManager(multi_manager=multi_manager)
    last_time = datetime.now()
    await multi_manager.setup_entry()
    LOGGER.debug(f"Xtended Tuya {entry.title} {datetime.now() - last_time} for setup_entry")

    # Get all devices from Tuya
    last_time = datetime.now()
    await multi_manager.update_device_cache()
    LOGGER.debug(f"Xtended Tuya {entry.title} {datetime.now() - last_time} for update_device_cache")

    # Connection is successful, store the manager & listener
    entry.runtime_data = HomeAssistantXTData(
        multi_manager=multi_manager,
        listener=multi_manager.multi_device_listener,
        service_manager=service_manager,
    )

    # Cleanup device registry
    last_time = datetime.now()
    XTEventLoopProtector.execute_out_of_event_loop(cleanup_device_registry, hass, multi_manager, entry)
    LOGGER.debug(f"Xtended Tuya {entry.title} {datetime.now() - last_time} for cleanup_device_registry")

    # Register known device IDs
    last_time = datetime.now()
    device_registry = dr.async_get(hass)
    aggregated_device_map = multi_manager.device_map
    for device in aggregated_device_map.values():
        XTEntity.mark_overriden_entities_as_disables(hass, device)
        XTEntity.register_current_entities_as_handled_dpcode(hass, device)
        multi_manager.virtual_state_handler.apply_init_virtual_states(device)
    LOGGER.debug(f"Xtended Tuya {entry.title} {datetime.now() - last_time} for device id registration")

    last_time = datetime.now()
    for device in aggregated_device_map.values():
        domain_identifiers: list = multi_manager.get_domain_identifiers_of_device(
            device.id
        )
        identifiers: set[tuple[str, str]] = set()
        if device_registry.async_get_device({(DOMAIN_ORIG, device.id)}) is not None:
            identifiers.add((DOMAIN_ORIG, device.id))

        for domain_identifier in domain_identifiers:
            identifiers.add((domain_identifier, device.id))
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers=identifiers,
            manufacturer="Tuya",
            name=device.name,
            model=f"{device.product_name} (unsupported)",
        )
    LOGGER.debug(f"Xtended Tuya {entry.title} {datetime.now() - last_time} for create device")

    last_time = datetime.now()
    await multi_manager.setup_entity_parsers()
    LOGGER.debug(f"Xtended Tuya {entry.title} {datetime.now() - last_time} for setup_entity_parsers")

    last_time = datetime.now()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    LOGGER.debug(f"Xtended Tuya {entry.title} {datetime.now() - last_time} for async_forward_entry_setups")

    # If the device does not register any entities, the device does not need to subscribe
    # So the subscription is here
    last_time = datetime.now()
    await XTEventLoopProtector.execute_out_of_event_loop_and_return(multi_manager.refresh_mq)
    LOGGER.debug(f"Xtended Tuya {entry.title} {datetime.now() - last_time} for refresh_mq")

    last_time = datetime.now()
    service_manager.register_services()
    LOGGER.debug(f"Xtended Tuya {entry.title} {datetime.now() - last_time} for register_services")

    last_time = datetime.now()
    XTEventLoopProtector.execute_out_of_event_loop(cleanup_duplicated_devices, hass, entry)
    LOGGER.debug(f"Xtended Tuya {entry.title} {datetime.now() - last_time} for cleanup_duplicated_devices")

    last_time = datetime.now()
    await multi_manager.on_loading_finalized(hass, entry)
    LOGGER.debug(f"Xtended Tuya {entry.title} {datetime.now() - last_time} for on_loading_finalized")
    LOGGER.debug(f"Xtended Tuya {entry.title} loaded in {datetime.now() - start_time}")
    return True


async def cleanup_duplicated_devices(
    hass: HomeAssistant, current_entry: ConfigEntry
) -> None:
    if not is_config_entry_master(hass, DOMAIN, current_entry):
        return
    while not are_all_domain_config_loaded(hass, DOMAIN, current_entry):
        await asyncio.sleep(0.1)
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    duplicate_check_table: dict[str, list] = {}
    for hass_dev_id, device_entry in list(device_registry.devices.items()):
        for item in device_entry.identifiers:
            if len(item) > 1:
                domain = item[0]
                device_id = item[1]
                if domain in [DOMAIN, DOMAIN_ORIG]:
                    if device_id not in duplicate_check_table:
                        duplicate_check_table[device_id] = []
                    if hass_dev_id not in duplicate_check_table[device_id]:
                        duplicate_check_table[device_id].append(hass_dev_id)
                    break
    for device_id in duplicate_check_table:
        remaining_devices = len(duplicate_check_table[device_id])
        if remaining_devices > 1:
            for hass_dev_id in duplicate_check_table[device_id]:
                if hass_dev_id not in device_registry.devices:
                    continue
                if remaining_devices > 1:
                    hass_entities = er.async_entries_for_device(
                        entity_registry,
                        device_id=hass_dev_id,
                        include_disabled_entities=True,
                    )
                    if len(hass_entities) == 0:
                        remaining_devices = remaining_devices - 1
                        try:
                            device_registry.async_remove_device(hass_dev_id)
                        except Exception:
                            # Discard any exception in device cleanup...
                            pass
                else:
                    break


async def cleanup_device_registry(
    hass: HomeAssistant, multi_manager: MultiManager, current_entry: ConfigEntry
) -> None:
    """Remove deleted device registry entry if there are no remaining entities."""
    if not is_config_entry_master(hass, DOMAIN, current_entry):
        return
    while not are_all_domain_config_loaded(hass, DOMAIN_ORIG, None):
        await asyncio.sleep(0.1)
    while not are_all_domain_config_loaded(hass, DOMAIN, current_entry):
        await asyncio.sleep(0.1)
    device_registry = dr.async_get(hass)
    for dev_id, device_entry in list(device_registry.devices.items()):
        for item in device_entry.identifiers:
            if not is_device_in_domain_device_maps(
                hass, [DOMAIN_ORIG, DOMAIN], item, None, True
            ):
                device_registry.async_remove_device(dev_id)
                break


def are_all_domain_config_loaded(
    hass: HomeAssistant, domain: str, current_entry: ConfigEntry | None
) -> bool:
    config_entries = hass.config_entries.async_entries(domain, False, False)
    for config_entry in config_entries:
        if (
            current_entry is not None
            and config_entry.entry_id == current_entry.entry_id
        ):
            continue
        if config_entry.state == ConfigEntryState.SETUP_IN_PROGRESS:
            return False
    return True


def is_config_entry_master(
    hass: HomeAssistant, domain: str, current_entry: ConfigEntry
) -> bool:
    config_entries = hass.config_entries.async_entries(domain, False, False)
    if len(config_entries) > 0:
        return config_entries[0] == current_entry
    return False


async def async_unload_entry(hass: HomeAssistant, entry: XTConfigEntry) -> bool:
    """Unloading the Tuya platforms."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        tuya = entry.runtime_data
        if tuya.manager is not None:
            if tuya.manager.mq is not None:
                tuya.manager.mq.stop()
            tuya.manager.remove_device_listeners()
            await XTEventLoopProtector.execute_out_of_event_loop_and_return(tuya.manager.unload)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: XTConfigEntry) -> None:
    """Remove a config entry.

    This will revoke the credentials from Tuya.
    """
    runtime_data = get_config_entry_runtime_data(hass, entry, DOMAIN)
    if runtime_data:
        await XTEventLoopProtector.execute_out_of_event_loop_and_return(runtime_data.device_manager.unload)
