from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import (
    DOMAIN_ORIG,
)
from ...util import (
    ConfigEntryRuntimeData,
    get_overriden_config_entry,
    get_config_entry_runtime_data,
)

def get_overriden_tuya_integration_runtime_data(hass: HomeAssistant, entry: ConfigEntry) -> ConfigEntryRuntimeData | None:
    if (overriden_config_entry := get_overriden_config_entry(hass,entry, DOMAIN_ORIG)):
        return get_config_entry_runtime_data(hass, overriden_config_entry, DOMAIN_ORIG)
    return None