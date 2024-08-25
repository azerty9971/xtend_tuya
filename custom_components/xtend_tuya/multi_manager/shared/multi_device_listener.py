from __future__ import annotations

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers import device_registry as dr

from ...const import (
    TUYA_HA_SIGNAL_UPDATE_ENTITY,
    TUYA_HA_SIGNAL_UPDATE_ENTITY_ORIG,
    TUYA_DISCOVERY_NEW,
    TUYA_DISCOVERY_NEW_ORIG,
    LOGGER,
    DOMAIN,
    DOMAIN_ORIG,
)

from ..multi_manager import (
    MultiManager,
    XTDevice,
)


class MultiDeviceListener:
    def __init__(self, hass: HomeAssistant, multi_manager: MultiManager) -> None:
        self.multi_manager = multi_manager
        self.hass = hass

    def update_device(self, device: XTDevice):
        if self.multi_manager.device_watcher.is_watched(device.id):
            LOGGER.warning(f"WD: update_device => {device.id}")
        devices = self.multi_manager.get_devices_from_device_id(device.id)
        for cur_device in devices:
            XTDevice.copy_data_from_device(device, cur_device)
        #if self.multi_manager.sharing_acount and self.multi_manager.sharing_acount.reuse_config:
        dispatcher_send(self.hass, f"{TUYA_HA_SIGNAL_UPDATE_ENTITY_ORIG}_{device.id}")
        dispatcher_send(self.hass, f"{TUYA_HA_SIGNAL_UPDATE_ENTITY}_{device.id}")

    def add_device(self, device: XTDevice):
        self.hass.add_job(self.async_remove_device, device.id)
        for account in self.multi_manager.accounts.values():
            account.on_add_device(device)
        dispatcher_send(self.hass, TUYA_DISCOVERY_NEW, [device.id])

    def remove_device(self, device_id: str):
        #log_stack("DeviceListener => async_remove_device")
        device_registry = dr.async_get(self.hass)
        identifiers: set = {}
        account_identifiers: set = {}
        for account in self.multi_manager.accounts.values():
            for account_identifier in account.get_device_registry_identifiers():
                if account_identifier not in account_identifiers:
                    identifiers.add(tuple(account_identifier, device_id))
                    account_identifiers.add(account_identifier)
        device_entry = device_registry.async_get_device(
            identifiers=identifiers
        )
        if device_entry is not None:
            device_registry.async_remove_device(device_entry.id)
    
    @callback
    def async_remove_device(self, device_id: str) -> None:
        """Remove device from Home Assistant."""
        #log_stack("DeviceListener => async_remove_device")
        device_registry = dr.async_get(self.hass)
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN_ORIG, device_id), (DOMAIN, device_id)}
        )
        if device_entry is not None:
            device_registry.async_remove_device(device_entry.id)