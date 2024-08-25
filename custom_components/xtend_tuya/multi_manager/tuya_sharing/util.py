from __future__ import annotations

from typing import (
    NamedTuple,
)

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from tuya_sharing import (
    Manager as TuyaSharingManager,
    SharingDeviceListener,
)
from .const import (
    DOMAIN_ORIG,
)
from ...util import (
    get_overriden_config_entry,
)

class TuyaIntegrationRuntimeData(NamedTuple):
    device_manager: TuyaSharingManager
    device_listener: SharingDeviceListener
    generic_runtime_data: any

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
            if hasattr(runtime_data, "device_listener"):
                device_listener = runtime_data.device_listener
            if hasattr(runtime_data, "listener"):
                device_listener = runtime_data.listener
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