"""Utility methods for the Tuya integration."""

from __future__ import annotations
import traceback 
import copy
from typing import NamedTuple
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import EntityDescription
from .const import (
    DPType,
    LOGGER,
    DOMAIN,
    DOMAIN_ORIG,
)

from tuya_sharing import (
    Manager as TuyaSharingManager,
    SharingDeviceListener,

)

from .multi_manager import (
    MultiManager,
    XTConfigEntry,
)

class TuyaIntegrationRuntimeData(NamedTuple):
    device_manager: TuyaSharingManager
    device_listener: SharingDeviceListener
    generic_runtime_data: any

class LogStackException(Exception):
    pass

def log_stack(message: str):
    stack = traceback.format_stack()
    LOGGER.debug(message)
    for stack_line in stack:
        LOGGER.debug(stack_line)

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

def determine_property_type(type, value = None) -> DPType:
        if type == "value":
            return DPType(DPType.INTEGER)
        if type == "bitmap":
            return DPType(DPType.RAW)
        if type == "enum":
            return DPType(DPType.ENUM)
        if type == "bool":
            return DPType(DPType.BOOLEAN)
        if type == "json":
            return DPType(DPType.JSON)
        if type == "string":
            return DPType(DPType.STRING)

def prepare_value_for_property_update(dp_item, value) -> str:
    #LOGGER.warning(f"prepare_value_for_property_update => {dp_item} <=> {value}")
    config_item = dp_item.get("config_item", None)
    if config_item is not None:
        value_type = config_item.get("valueType", None)
        if value_type is not None:
            if value_type == DPType.BOOLEAN:
                if bool(value):
                    return 'true'
                else:
                    return 'false'
    return str(value)

def get_domain_config_entries(hass: HomeAssistant, domain: str) -> list[ConfigEntry]:
    return hass.config_entries.async_entries(domain,False,False)

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

def get_tuya_integration_runtime_data(hass: HomeAssistant, entry: ConfigEntry, domain: str) -> TuyaIntegrationRuntimeData | None:
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
            device_listener = runtime_data.device_listener
    else:
        runtime_data = entry.runtime_data
        device_manager = entry.runtime_data.manager
        device_listener = entry.runtime_data.listener
    if device_manager:
        return TuyaIntegrationRuntimeData(device_manager=device_manager, generic_runtime_data=runtime_data, device_listener=device_listener)
    else:
        return None

def get_overriden_tuya_integration_runtime_data(hass: HomeAssistant, entry: ConfigEntry) -> TuyaIntegrationRuntimeData | None:
    if (overriden_config_entry := get_overriden_config_entry(hass,entry, DOMAIN_ORIG)):
        return get_tuya_integration_runtime_data(hass, overriden_config_entry, DOMAIN_ORIG)
    return None

def merge_device_descriptors(descriptors1, descriptors2):
    return_descriptors = copy.deepcopy(descriptors1)
    for category in descriptors2:
        if category not in descriptors1:
            #Merge the whole category
            return_descriptors[category] = copy.deepcopy(descriptors2[category])
        else:
            #Merge the content of the descriptor category
            return_descriptors[category] = merge_descriptor_category(descriptors1[category], descriptors2[category])
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

def merge_categories(category_list1, category_list2):
    return_list = copy.deepcopy(list(category_list1))
    for category in category_list2:
        if category not in return_list:
            return_list[category] = copy.deepcopy(category_list2[category])
    return return_list