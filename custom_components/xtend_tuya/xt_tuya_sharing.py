"""
This file contains all the code that inherit from Tuya integration
"""

from __future__ import annotations
from typing import Any

from homeassistant.core import HomeAssistant, callback

from tuya_sharing.manager import (
    Manager,
)
from tuya_sharing.customerapi import (
    CustomerApi,
    SharingTokenListener,
)
from tuya_sharing.home import (
    SmartLifeHome,
)
from tuya_sharing.device import (
    CustomerDevice,
    DeviceRepository,
    DeviceStatusRange,
)

from .const import (
    CONF_TOKEN_INFO,
    LOGGER,
)

from .multi_manager import (
    MultiManager,
)

class XTSharingTokenListener(SharingTokenListener):
    """Token listener for upstream token updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry, #: XTConfigEntry,
    ) -> None:
        """Init TokenListener."""
        self.hass = hass
        self.entry = entry

    def update_token(self, token_info: dict[str, Any]) -> None:
        """Update token info in config entry."""
        data = {
            **self.entry.data,
            CONF_TOKEN_INFO: {
                "t": token_info["t"],
                "uid": token_info["uid"],
                "expire_time": token_info["expire_time"],
                "access_token": token_info["access_token"],
                "refresh_token": token_info["refresh_token"],
            },
        }

        @callback
        def async_update_entry() -> None:
            """Update config entry."""
            self.hass.config_entries.async_update_entry(self.entry, data=data)

        self.hass.add_job(async_update_entry)

class XTSharingDeviceManager(Manager):
    def __init__(
        self,
        multi_manager: MultiManager,
        other_device_manager: Manager = None
    ) -> None:
        self.multi_manager = multi_manager
        self.terminal_id = None
        self.mq = None
        self.customer_api = None
        self.home_repository = None
        self.device_repository = None
        self.scene_repository = None
        self.user_repository = None
        self.device_map: dict[str, CustomerDevice] = {}
        self.user_homes: list[SmartLifeHome] = []
        self.device_listeners = set()
        self.other_device_manager = other_device_manager
    
    def on_external_refresh_mq(self):
        if self.other_device_manager is not None:
            self.mq = self.other_device_manager.mq
            self.mq.add_message_listener(self.multi_manager.on_message_from_tuya_sharing)
            self.mq.remove_message_listener(self.other_device_manager.on_message)

    def refresh_mq(self):
        if self.other_device_manager is not None:
            if self.mq and self.mq != self.other_device_manager.mq:
                self.mq.stop()
            self.other_device_manager.refresh_mq()
            return
        super().refresh_mq()
        self.mq.add_message_listener(self.multi_manager.on_message_from_tuya_sharing)
        self.mq.remove_message_listener(self.on_message)

    def set_overriden_device_manager(self, other_device_manager: Manager) -> None:
        self.other_device_manager = other_device_manager
    
    def get_overriden_device_manager(self) -> Manager | None:
        if self.other_device_manager is not None:
            return self.other_device_manager
        return None

    def _on_device_report(self, device_id: str, status: list):
        device = self.device_map.get(device_id, None)
        if not device:
            LOGGER.warning(f"_on_device_report sharing device not found : {device_id}")
            return
        status_new = self.multi_manager.convert_device_report_status_list(device_id, status)
        status_new = self.multi_manager.apply_virtual_states_to_status_list(device, status_new)
        super()._on_device_report(device_id, status_new)
    
    def send_commands(
            self, device_id: str, commands: list[dict[str, Any]]
    ):
        if other_manager := self.get_overriden_device_manager():
            other_manager.send_commands(device_id, commands)
            return
        super().send_commands(device_id, commands)

class XTSharingDeviceRepository(DeviceRepository):
    def __init__(self, customer_api: CustomerApi, manager: XTSharingDeviceManager, multi_manager: MultiManager):
        super().__init__(customer_api)
        self.manager = manager
        self.multi_manager = multi_manager

    def update_device_specification(self, device: CustomerDevice):
        super().update_device_specification(device)
        if device.id == "bfd373337fcd1752dbs9b4":
            LOGGER.warning(f"update_device_specification: {device.status_range}")

    def update_device_strategy_info(self, device: CustomerDevice):
        super().update_device_strategy_info(device)
        for loc_strat in device.local_strategy.values():
            if "statusCode" not in loc_strat or "valueType" not in loc_strat:
                continue
            code = loc_strat["statusCode"]
            value_type = loc_strat["valueType"]
            
            #Sometimes the Type provided by Tuya is ill formed,
            #replace it with the one from the local strategy
            if code in device.status_range:
                device.status_range[code].type   = value_type
            if code in device.function:
                device.function[code].type   = value_type

            if (
                "valueDesc"  in loc_strat and
                code not in device.status_range and
                code not in device.function
                ):
                device.status_range[code] = DeviceStatusRange()
                device.status_range[code].code   = code
                device.status_range[code].type   = value_type
                device.status_range[code].values = loc_strat["valueDesc"]
        self.multi_manager.apply_init_virtual_states(device)
        self.multi_manager.allow_virtual_devices_not_set_up(device)