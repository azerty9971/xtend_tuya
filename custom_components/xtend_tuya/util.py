"""Utility methods for the Tuya integration."""

from __future__ import annotations
import copy
import traceback
from typing import NamedTuple
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import EntityDescription
from .const import (
    LOGGER,
    DPType,
    DOMAIN,
)

from tuya_sharing.manager import (
    Manager,
    SharingDeviceListener,
)

from .multi_manager.multi_manager import (
    MultiManager,
    XTConfigEntry,
    XTDevice,
)

def log_stack(message: str):
    LOGGER.debug(message, stack_info=True)

def get_default_value(dp_type: DPType) -> any:
    match dp_type:
        case DPType.BOOLEAN:
            return False
        case DPType.ENUM:
            return None
        case DPType.INTEGER:
            return 0
        case DPType.JSON:
            return "{}"
        case DPType.RAW:
            return None
        case DPType.STRING:
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
    generic_runtime_data: any

def get_config_entry_runtime_data(hass: HomeAssistant, entry: ConfigEntry, domain: str) -> ConfigEntryRuntimeData | None:
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
    if device_manager is not None:
        return ConfigEntryRuntimeData(device_manager=device_manager, generic_runtime_data=runtime_data, device_listener=device_listener)
    else:
        return None

def get_domain_config_entries(hass: HomeAssistant, domain: str) -> list[ConfigEntry]:
    return hass.config_entries.async_entries(domain, False, False)

def get_overriden_config_entry(hass: HomeAssistant, entry: XTConfigEntry, other_domain: str) -> ConfigEntry:
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
            #Merge the whole category
            return_descriptors[category] = copy.deepcopy(descriptors2[category])
        else:
            #Merge the content of the descriptor category
            return_descriptors[category] = merge_descriptor_category(return_descriptors[category], descriptors2[category])
    return return_descriptors

def merge_descriptor_category(category1: tuple[EntityDescription, ...], category2: tuple[EntityDescription, ...]):
    descriptor1_key_list = []
    return_category = copy.deepcopy(list(category1))
    for descriptor in category1:
        if descriptor.key not in descriptor1_key_list:
            descriptor1_key_list.append(descriptor.key)
    for descriptor in category2:
        if descriptor.key not in descriptor1_key_list:
            return_category.append(copy.deepcopy(descriptor))
    return tuple(return_category)

def append_dictionnaries(dict1: dict, dict2: dict) -> dict:
    return_dict = copy.deepcopy(dict1)
    for category in dict2:
        if category not in return_dict:
            return_dict[category] = copy.deepcopy(dict2[category])
    return return_dict

def append_lists(list1: list, list2: list) -> list:
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

def get_all_multi_managers(hass: HomeAssistant) -> list[MultiManager]:
    return_list: list[MultiManager] = []
    config_entries = get_domain_config_entries(hass, DOMAIN)
    for config_entry in config_entries:
        if runtime_data := get_config_entry_runtime_data(hass, config_entry, DOMAIN):
            return_list.append(runtime_data.device_manager)
    return return_list

def get_device_multi_manager(hass: HomeAssistant, device: XTDevice) -> MultiManager | None:
    all_mm = get_all_multi_managers(hass=hass)
    for mm in all_mm:
        if device.id in mm.device_map:
            return mm
    return None