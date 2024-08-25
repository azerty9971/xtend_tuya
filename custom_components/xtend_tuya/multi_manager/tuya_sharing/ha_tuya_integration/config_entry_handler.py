from __future__ import annotations

from homeassistant.core import HomeAssistant
import homeassistant.components.tuya as tuya_integration

from ....const import (
    DOMAIN_ORIG,
#    LOGGER,
)
from ...multi_manager import (
    XTConfigEntry,
)
from ..xt_tuya_sharing_manager import (
    XTSharingDeviceManager,
)
from ..util import (
    get_tuya_integration_runtime_data,
)

class XTHATuyaIntegrationConfigEntryManager:
    def __init__(self, manager: XTSharingDeviceManager, config_entry: XTConfigEntry) -> None:
        self.manager = manager
        self.config_entry = config_entry

    def on_tuya_refresh_mq(self, before_call: bool):
        if not before_call:
            self.manager.on_external_refresh_mq()
    
    async def on_tuya_setup_entry(self, before_call: bool, hass: HomeAssistant, entry: tuya_integration.TuyaConfigEntry):
        #LOGGER.warning(f"on_tuya_setup_entry {before_call} : {entry.__dict__}")
        if not before_call and self.config_entry.title == entry.title:
            hass.config_entries.async_schedule_reload(self.config_entry.entry_id)


    async def on_tuya_unload_entry(self, before_call: bool, hass: HomeAssistant, entry: tuya_integration.TuyaConfigEntry):
        #LOGGER.warning(f"on_tuya_unload_entry {before_call} : {entry.__dict__}")
        if before_call:
            #If before the call, we need to add the regular device listener back
            runtime_data = get_tuya_integration_runtime_data(hass, entry, DOMAIN_ORIG)
            runtime_data.device_manager.add_device_listener(runtime_data.device_listener)
        else:
            if self.config_entry.title == entry.title:
                self.manager.reuse_config = False
                self.manager.set_overriden_device_manager(None)
                self.manager.mq = None

    async def on_tuya_remove_entry(self, before_call: bool, hass: HomeAssistant, entry: tuya_integration.TuyaConfigEntry):
        #LOGGER.warning(f"on_tuya_remove_entry {before_call} : {entry.__dict__}")
        if not before_call and self.manager.sharing_account and self.config_entry.title == entry.title:
            self.manager.reuse_config = False
            self.manager.set_overriden_device_manager(None)
            self.manager.mq = None
            self.manager.refresh_mq()