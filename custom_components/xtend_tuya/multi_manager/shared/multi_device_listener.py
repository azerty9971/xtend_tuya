from __future__ import annotations
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers import device_registry as dr
from ...const import (
    LOGGER,  # noqa: F401
    DOMAIN,
    DOMAIN_ORIG,
)
import custom_components.xtend_tuya.multi_manager.multi_manager as mm
import custom_components.xtend_tuya.multi_manager.shared.shared_classes as sh
import custom_components.xtend_tuya.util as util


class MultiDeviceListener:
    def __init__(self, hass: HomeAssistant, multi_manager: mm.MultiManager) -> None:
        self.multi_manager = multi_manager
        self.hass = hass

    def update_device(
        self, device: sh.XTDevice, updated_status_properties: list[str] | None = None
    ):
        signal_list: list[str] = []
        for account in self.multi_manager.accounts.values():
            signal_list = util.append_lists(
                signal_list, account.on_update_device(device)
            )
        self.trigger_device_discovery(device, signal_list, updated_status_properties)

    def trigger_device_discovery(
        self,
        device: sh.XTDevice,
        signal_list: list[str],
        updated_status_properties: list[str] | None = None,
    ):
        for signal in signal_list:
            try:
                dispatcher_send(
                    self.hass, f"{signal}_{device.id}", updated_status_properties
                )
            except Exception as e:
                # Could happen upon restart of HA
                LOGGER.debug(
                    f"Could not send {signal}_{device.id} (updated_status_properties = {updated_status_properties}) to dispatch: {e}"
                )

    def add_device(self, device: sh.XTDevice):
        self.hass.add_job(self.async_remove_device, device.id)
        signal_list: list[str] = []
        for account in self.multi_manager.accounts.values():
            signal_list = util.append_lists(signal_list, account.on_add_device(device))
        for signal in signal_list:
            dispatcher_send(self.hass, signal, [device.id])

    def remove_device(self, device_id: str):
        # log_stack("DeviceListener => async_remove_device")
        device_registry = dr.async_get(self.hass)
        identifiers: set = set()
        account_identifiers: set = set()
        for account in self.multi_manager.accounts.values():
            for account_identifier in account.get_device_registry_identifiers():
                if account_identifier not in account_identifiers:
                    identifiers.add((account_identifier, device_id))
                    account_identifiers.add(account_identifier)
        device_entry = device_registry.async_get_device(identifiers=identifiers)
        if device_entry is not None:
            device_registry.async_remove_device(device_entry.id)

    @callback
    def async_remove_device(self, device_id: str) -> None:
        """Remove device from Home Assistant."""
        # log_stack("DeviceListener => async_remove_device")
        device_registry = dr.async_get(self.hass)
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN_ORIG, device_id), (DOMAIN, device_id)}
        )
        if device_entry is not None:
            device_registry.async_remove_device(device_entry.id)
