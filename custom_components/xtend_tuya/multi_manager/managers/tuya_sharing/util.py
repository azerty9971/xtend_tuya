from __future__ import annotations
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.exceptions import ConfigEntryNotReady
from .const import (
    DOMAIN_ORIG,
)
from ....util import (
    ConfigEntryRuntimeData,
    get_overriden_config_entry,
    get_config_entry_runtime_data,
)


# States that mean the overriden Tuya entry has not finished setting up yet
# (so its runtime_data is absent or partially initialised). Seen on installs
# with many devices where official Tuya is slow and xtend_tuya races ahead.
_TUYA_NOT_READY_STATES = (
    ConfigEntryState.NOT_LOADED,
    ConfigEntryState.SETUP_IN_PROGRESS,
    ConfigEntryState.SETUP_RETRY,
)


def get_overriden_tuya_integration_runtime_data(
    hass: HomeAssistant, entry: ConfigEntry
) -> ConfigEntryRuntimeData | None:
    overriden_config_entry = get_overriden_config_entry(hass, entry, DOMAIN_ORIG)
    if not overriden_config_entry:
        # No official Tuya entry overrides us → genuine standalone setup.
        return None
    runtime_data = get_config_entry_runtime_data(
        hass, overriden_config_entry, DOMAIN_ORIG
    )
    if runtime_data is None and overriden_config_entry.state in _TUYA_NOT_READY_STATES:
        # The override entry exists but Tuya hasn't finished setting up. Defer
        # so HA retries us once Tuya is LOADED, instead of crashing (old
        # behaviour) or silently falling back to a degraded standalone setup.
        raise ConfigEntryNotReady(
            f"Tuya integration entry '{overriden_config_entry.title}' is not "
            "ready yet; deferring xtend_tuya setup until Tuya has finished."
        )
    return runtime_data
