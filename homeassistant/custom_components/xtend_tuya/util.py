"""Utility methods for the Tuya integration."""
from __future__ import annotations
from .const import (
    DOMAIN, 
    DOMAIN_ORIG,CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_APP_TYPE,
    CONF_AUTH_TYPE,
    CONF_COUNTRY_CODE,
    CONF_ENDPOINT,
    CONF_PASSWORD,
    CONF_PROJECT_TYPE,
    CONF_USERNAME )
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from . import HomeAssistantTuyaData

def remap_value(
    value: float | int,
    from_min: float | int = 0,
    from_max: float | int = 255,
    to_min: float | int = 0,
    to_max: float | int = 255,
    reverse: bool = False,
) -> float:
    """Remap a value from its current range, to a new range."""
    if reverse:
        value = from_max - value + from_min
    return ((value - from_min) / (from_max - from_min)) * (to_max - to_min) + to_min

class ConfigMapper:
    @staticmethod
    def get_tuya_data(hass: HomeAssistant, entry: ConfigEntry) -> HomeAssistantTuyaData:
        if DOMAIN_ORIG in hass.data:
            tuya_data = hass.data[DOMAIN_ORIG]
            for config in tuya_data:
                config_entry = hass.config_entries.async_get_entry(config)
                if (
                    entry.data[CONF_ENDPOINT]           == config_entry.data[CONF_ENDPOINT]
                    and entry.data[CONF_ACCESS_ID]      == config_entry.data[CONF_ACCESS_ID]
                    and entry.data[CONF_ACCESS_SECRET]  == config_entry.data[CONF_ACCESS_SECRET]
                    and entry.data[CONF_AUTH_TYPE]      == config_entry.data[CONF_AUTH_TYPE]
                    and entry.data[CONF_USERNAME]       == config_entry.data[CONF_USERNAME]
                    and entry.data[CONF_PASSWORD]       == config_entry.data[CONF_PASSWORD]
                    and entry.data[CONF_COUNTRY_CODE]   == config_entry.data[CONF_COUNTRY_CODE]
                    and entry.data[CONF_APP_TYPE]       == config_entry.data[CONF_APP_TYPE]
                ):
                    return hass.data[DOMAIN_ORIG][config_entry.entry_id]
        return hass.data[DOMAIN][entry.entry_id]