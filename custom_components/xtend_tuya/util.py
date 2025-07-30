"""Utility methods for the Tuya integration."""

from __future__ import annotations
import copy
from typing import NamedTuple, Any
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import EntityDescription
from .const import (
    LOGGER,
    DOMAIN,
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
