from __future__ import annotations

import voluptuous as vol
from dataclasses import dataclass
from homeassistant.core import HomeAssistant
from .shared_data_entry import (
    XTFlowDataBase,
    XTDataEntryManager,
    ConfigFlow,
    ConfigFlowResult,
    DiscoveryInfoType,
    cast,
)
from ....const import (
    LOGGER,
    XTIRHubInformation,
    XTIRRemoteInformation,
)
import custom_components.xtend_tuya.multi_manager.multi_manager as mm


@dataclass
class XTFlowDataAddIRDevice(XTFlowDataBase):
    device: mm.XTDevice


@dataclass
class XTFlowDataAddIRDeviceKey(XTFlowDataBase):
    device: mm.XTDevice
    hub: XTIRHubInformation
    remote: XTIRRemoteInformation
    key_name: str | None = None


class XTDataEntryAddIRDevice(XTDataEntryManager):

    def start_add_ir_device_flow(
        self, hass: HomeAssistant, multi_manager: mm.MultiManager, device: mm.XTDevice
    ):
        flow_data = XTFlowDataAddIRDevice(
            flow_id=None,
            multi_manager=multi_manager,
            hass=hass,
            schema=vol.Schema(
                {
                    vol.Required("TEST", default="26"): str,
                }
            ),
            title=f"Add new IR device ({device.name})",
            device=device,
            processing_callback=None,
        )
        XTDataEntryManager.show_user_input(self, flow_data)

    def user_interaction_callback(
        self,
        config_flow: ConfigFlow,
        flow_data: XTFlowDataBase,
        discovery_info: DiscoveryInfoType | None,
    ) -> ConfigFlowResult:
        LOGGER.warning(
            f"Calling XTDataEntryAddIRDevice->user_interaction_callback: flow_data: {flow_data}, discovery_info: {discovery_info}"
        )

        return self.async_abort(config_flow=config_flow, reason="")


class XTDataEntryAddIRDeviceKey(XTDataEntryManager):

    def start_add_ir_device_key_flow(
        self,
        hass: HomeAssistant,
        multi_manager: mm.MultiManager,
        device: mm.XTDevice,
        hub: XTIRHubInformation,
        remote: XTIRRemoteInformation,
    ):
        flow_data = XTFlowDataAddIRDeviceKey(
            flow_id=None,
            multi_manager=multi_manager,
            hass=hass,
            schema=vol.Schema(
                {
                    vol.Required("Please enter a key name", default=""): str,
                }
            ),
            title=f"Add new key for {device.name}",
            device=device,
            processing_callback=None,
            hub=hub,
            remote=remote
        )
        XTDataEntryManager.show_user_input(self, flow_data)

    def user_interaction_callback(
        self,
        config_flow: ConfigFlow,
        flow_data: XTFlowDataBase,
        discovery_info: DiscoveryInfoType | None,
    ) -> ConfigFlowResult:
        LOGGER.warning(
            f"Calling XTDataEntryAddIRDevice->user_interaction_callback: flow_data: {flow_data}, discovery_info: {discovery_info}"
        )
        real_flow_data = cast(XTFlowDataAddIRDeviceKey, flow_data)
        if discovery_info is not None:
            LOGGER.warning(f"Showed discovery info: {discovery_info}")
        if real_flow_data.key_name is None:
            return self.async_show_form(config_flow=config_flow, data_schema=vol.Schema(
                {
                    vol.Required("Please enter a key name", default=""): str,
                }
            ))
        return self.async_abort(config_flow=config_flow, reason="")
