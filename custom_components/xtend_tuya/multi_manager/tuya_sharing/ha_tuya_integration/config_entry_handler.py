from __future__ import annotations

from homeassistant.core import HomeAssistant
import homeassistant.components.tuya as tuya_integration

from ....const import (
    DOMAIN_ORIG,
    LOGGER,
)
from ...multi_manager import (
    MultiManager,
    XTConfigEntry,
)
from ....util import (
    get_tuya_integration_runtime_data,
)

class XTHATuyaIntegrationConfigEntryManager:
    def __init__(self, multi_manager: MultiManager, config_entry: XTConfigEntry) -> None:
        self.multi_manager = multi_manager
        self.config_entry = config_entry

    def on_tuya_refresh_mq(self, before_call: bool):
        if not before_call and self.multi_manager.sharing_account:
            self.multi_manager.sharing_account.device_manager.on_external_refresh_mq()
    
    async def on_tuya_setup_entry(self, before_call: bool, hass: HomeAssistant, entry: tuya_integration.TuyaConfigEntry):
        #LOGGER.warning(f"on_tuya_setup_entry {before_call} : {entry.__dict__}")
        if not before_call and self.multi_manager.sharing_account and self.config_entry.title == entry.title:
            hass.config_entries.async_schedule_reload(self.config_entry.entry_id)


    async def on_tuya_unload_entry(self, before_call: bool, hass: HomeAssistant, entry: tuya_integration.TuyaConfigEntry):
        #LOGGER.warning(f"on_tuya_unload_entry {before_call} : {entry.__dict__}")
        if before_call:
            #If before the call, we need to add the regular device listener back
            runtime_data = get_tuya_integration_runtime_data(hass, entry, DOMAIN_ORIG)
            runtime_data.device_manager.add_device_listener(runtime_data.device_listener)
        else:
            if self.multi_manager.sharing_account and self.config_entry.title == entry.title:
                self.reuse_config = False
                self.multi_manager.sharing_account.device_manager.set_overriden_device_manager(None)
                self.multi_manager.sharing_account.device_manager.mq = None

    async def on_tuya_remove_entry(self, before_call: bool, hass: HomeAssistant, entry: tuya_integration.TuyaConfigEntry):
        #LOGGER.warning(f"on_tuya_remove_entry {before_call} : {entry.__dict__}")
        if not before_call and self.multi_manager.sharing_account and self.config_entry.title == entry.title:
            self.reuse_config = False
            self.multi_manager.sharing_account.device_manager.set_overriden_device_manager(None)
            self.multi_manager.sharing_account.device_manager.mq = None
            self.multi_manager.sharing_account.device_manager.refresh_mq()
    
    async def overriden_tuya_entry_updated(self, hass: HomeAssistant, config_entry: tuya_integration.TuyaConfigEntry) -> None:
        LOGGER.warning("overriden_tuya_entry_updated")