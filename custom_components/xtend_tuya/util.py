"""Utility methods for the Tuya integration."""

from __future__ import annotations
import traceback 
from typing import NamedTuple
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import (
    DPType,
    LOGGER,
    DOMAIN,
    DOMAIN_ORIG,
)

from tuya_sharing import (
    Manager as TuyaSharingManager,
)

from .multi_manager import (
    MultiManager,
    XTConfigEntry,
)

class TuyaIntegrationRuntimeData(NamedTuple):
    device_manager: TuyaSharingManager
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
            device_manager = runtime_data.manager
    else:
        runtime_data = entry.runtime_data
        device_manager = entry.runtime_data.manager
    if device_manager:
        return TuyaIntegrationRuntimeData(device_manager=device_manager, generic_runtime_data=runtime_data)
    else:
        return None

def get_overriden_tuya_integration_runtime_data(hass: HomeAssistant, entry: ConfigEntry) -> TuyaIntegrationRuntimeData | None:
    if (overriden_config_entry := get_overriden_config_entry(hass,entry, DOMAIN_ORIG)):
        return get_tuya_integration_runtime_data(hass, overriden_config_entry, DOMAIN_ORIG)
    return None, None