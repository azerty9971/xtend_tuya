"""Utility methods for the Tuya integration."""

from __future__ import annotations
import copy
from typing import NamedTuple, Any
from datetime import datetime
from base64 import b64decode
from homeassistant.util.dt import DEFAULT_TIME_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.device_registry import (
    DeviceEntry,
)
from .const import (
    LOGGER,
    DOMAIN,
    DOMAIN_ORIG,
)
from tuya_sharing.manager import (
    Manager,
    SharingDeviceListener,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaDPType,
)
import custom_components.xtend_tuya.multi_manager.multi_manager as mm
import custom_components.xtend_tuya.multi_manager.shared.shared_classes as shared


def log_stack(message: str):
    LOGGER.debug(message, stack_info=True)


def get_default_value(dp_type: TuyaDPType | None) -> Any:
    if dp_type is None:
        return None
    match dp_type:
        case TuyaDPType.BOOLEAN:
            return False
        case TuyaDPType.ENUM:
            return None
        case TuyaDPType.INTEGER:
            return 0
        case TuyaDPType.JSON:
            return "{}"
        case TuyaDPType.RAW:
            return None
        case TuyaDPType.STRING:
            return ""
    return None


def remap_value(
    value: float,
    from_min: float = 0,
    from_max: float = 255,
    to_min: float = 0,
    to_max: float = 255,
    reverse: bool = False,
) -> float:
    """Remap a value from its current range, to a new range."""
    if reverse:
        value = from_max - value + from_min
    return ((value - from_min) / (from_max - from_min)) * (to_max - to_min) + to_min


class ConfigEntryRuntimeData(NamedTuple):
    device_manager: Manager
    device_listener: SharingDeviceListener
    generic_runtime_data: Any


def get_config_entry_runtime_data(
    hass: HomeAssistant, entry: ConfigEntry, domain: str
) -> ConfigEntryRuntimeData | None:
    if not entry:
        return None
    runtime_data = None
    device_manager = None
    device_listener = None
    if not hasattr(entry, "runtime_data") or entry.runtime_data is None:
        # Try to fetch the manager using the old way
        if domain in hass.data and entry.entry_id in hass.data[domain]:
            runtime_data = hass.data[domain][entry.entry_id]
            if hasattr(runtime_data, "device_manager"):
                device_manager = runtime_data.device_manager
            if hasattr(runtime_data, "manager"):
                device_manager = runtime_data.manager
            if hasattr(runtime_data, "device_listener"):
                device_listener = runtime_data.device_listener
            if hasattr(runtime_data, "listener"):
                device_listener = runtime_data.listener
    else:
        runtime_data = entry.runtime_data
        device_manager = entry.runtime_data.manager
        device_listener = entry.runtime_data.listener
    if device_manager is not None and device_listener is not None:
        return ConfigEntryRuntimeData(
            device_manager=device_manager,
            generic_runtime_data=runtime_data,
            device_listener=device_listener,
        )
    else:
        return None


def get_domain_config_entries(hass: HomeAssistant, domain: str) -> list[ConfigEntry]:
    return hass.config_entries.async_entries(domain, False, False)


def get_overriden_config_entry(
    hass: HomeAssistant, entry: shared.XTConfigEntry, other_domain: str
) -> ConfigEntry | None:
    other_domain_config_entries = get_domain_config_entries(hass, other_domain)
    for od_config_entry in other_domain_config_entries:
        if entry.title == od_config_entry.title:
            return od_config_entry
    return None


def merge_iterables(iter1, iter2):
    for item1 in iter1:
        if item1 not in iter2:
            iter2[item1] = copy.deepcopy(iter1[item1])
    for item2 in iter2:
        if item2 not in iter1:
            iter1[item2] = copy.deepcopy(iter2[item2])


def merge_device_descriptors(descriptors1, descriptors2):
    return_descriptors = copy.deepcopy(descriptors1)
    for category in descriptors2:
        if category not in return_descriptors:
            # Merge the whole category
            return_descriptors[category] = copy.deepcopy(descriptors2[category])
        else:
            # Merge the content of the descriptor category
            return_descriptors[category] = merge_descriptor_category(
                return_descriptors[category], descriptors2[category]
            )
    return return_descriptors


def merge_descriptor_category(
    category1: tuple[EntityDescription, ...] | None,
    category2: tuple[EntityDescription, ...] | None,
) -> tuple[EntityDescription, ...]:
    if category1 is None and category2 is None:
        return tuple()
    elif category1 is None and category2 is not None:
        return category2
    elif category1 is not None and category2 is None:
        return category1
    elif category1 is not None and category2 is not None:
        descriptor1_key_list = []
        return_category = copy.deepcopy(list(category1))
        for descriptor in category1:
            if descriptor.key not in descriptor1_key_list:
                descriptor1_key_list.append(descriptor.key)
        for descriptor in category2:
            if descriptor.key not in descriptor1_key_list:
                return_category.append(copy.deepcopy(descriptor))
        return tuple(return_category)
    return tuple()


def restrict_descriptor_category(
    category: tuple[EntityDescription, ...] | None, restrict_to_keys: list[str]
) -> tuple[EntityDescription, ...]:
    return_list: list[EntityDescription] = []
    if category is None:
        return tuple(return_list)
    for descriptor in category:
        if descriptor.key in restrict_to_keys:
            return_list.append(descriptor)
    return tuple(return_list)


def append_dictionnaries(dict1: dict, dict2: dict) -> dict:
    return_dict = copy.deepcopy(dict1)
    for category in dict2:
        if category not in return_dict:
            return_dict[category] = copy.deepcopy(dict2[category])
    return return_dict


def append_lists(list1: list, list2: list | None) -> list:
    return_list = copy.deepcopy(list(list1))
    if list2:
        for item in list2:
            if item not in return_list:
                return_list.append(copy.deepcopy(item))
    return return_list


def append_sets(set1: set, set2: set) -> set:
    return_set = set(copy.deepcopy(set1))
    for item in set2:
        if item not in return_set:
            return_set.add(copy.deepcopy(item))
    return return_set


def append_tuples(tuple1: tuple, tuple2: tuple) -> tuple:
    return tuple(append_lists(list(tuple1), list(tuple2)))


def get_all_multi_managers(hass: HomeAssistant) -> list[mm.MultiManager]:
    return_list: list[mm.MultiManager] = []
    config_entries = get_domain_config_entries(hass, DOMAIN)
    for config_entry in config_entries:
        if runtime_data := get_config_entry_runtime_data(hass, config_entry, DOMAIN):
            return_list.append(runtime_data.device_manager)  # type: ignore
    return return_list


def get_device_multi_manager(
    hass: HomeAssistant, device: shared.XTDevice
) -> mm.MultiManager | None:
    all_multimanager = get_all_multi_managers(hass=hass)
    for multimanager in all_multimanager:
        if device.id in multimanager.device_map:
            return multimanager
    return None


def get_domain_device_map(
    hass: HomeAssistant,
    domain: str,
    except_of_entry: ConfigEntry | None = None,
    with_scene: bool = False,
) -> dict[str, Any]:
    device_map = {}
    config_entries = hass.config_entries.async_entries(domain, False, False)
    for config_entry in config_entries:
        if config_entry == except_of_entry:
            continue
        if runtime_data := get_config_entry_runtime_data(hass, config_entry, domain):
            for device_id in runtime_data.device_manager.device_map:
                if device_id not in device_map:
                    device_map[device_id] = runtime_data.device_manager.device_map[
                        device_id
                    ]
            if with_scene and hasattr(runtime_data.device_manager, "scene_id"):
                for scene_id in runtime_data.device_manager.scene_id:  # type: ignore
                    device_map[scene_id] = None
    return device_map


def is_device_in_domain_device_maps(
    hass: HomeAssistant,
    domains: list[str],
    device_entry_identifiers: tuple[str, str],
    except_of_entry: ConfigEntry | None = None,
    with_scene: bool = False,
):
    if len(device_entry_identifiers) > 1:
        device_domain = device_entry_identifiers[0]
    else:
        return True
    if device_domain in domains:
        for domain in domains:
            device_map = get_domain_device_map(
                hass, domain, except_of_entry, with_scene
            )
            device_id = device_entry_identifiers[1]
            if device_id in device_map:
                return True

    else:
        return True

    return False


def delete_all_device_entities(hass: HomeAssistant, device_ids: list[str], platform: Platform | None = None):
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    hass_devices: list[DeviceEntry] = []
    for device_id in device_ids:
        if hass_device := device_registry.async_get_device(
            identifiers={(DOMAIN, device_id), (DOMAIN_ORIG, device_id)}
        ):
            hass_devices.append(hass_device)
    for hass_device in hass_devices:
        hass_entities = er.async_entries_for_device(
            entity_registry,
            device_id=hass_device.id,
            include_disabled_entities=True,
        )
        for entity_entry in hass_entities:
            LOGGER.warning(f"Considering removal of {entity_entry.name} entry({entity_entry}) provided platform: {platform}")
            if platform is None or platform == entity_entry.platform:
                LOGGER.warning(f"Removed {entity_entry.name}")
                entity_registry.async_remove(entity_entry.entity_id)


# Decodes a b64-encoded timestamp
def b64todatetime(value):
    decoded_value = b64decode(value)
    try:
        return datetime(
            year=2000 + decoded_value[0],
            month=decoded_value[1],
            day=decoded_value[2],
            hour=decoded_value[3],
            minute=decoded_value[4],
            second=decoded_value[5],
            tzinfo=DEFAULT_TIME_ZONE,
        )
    except Exception:
        return None
