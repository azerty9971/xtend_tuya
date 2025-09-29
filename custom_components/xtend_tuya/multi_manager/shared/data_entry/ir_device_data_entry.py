from __future__ import annotations

import voluptuous as vol
from dataclasses import dataclass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import dispatcher_send
from .shared_data_entry import (
    XTFlowDataBase,
    XTDataEntryManager,
    ConfigFlow,
    ConfigFlowResult,
    DiscoveryInfoType,
    cast,
    Event,
)
from ....const import (
    LOGGER,
    XTIRHubInformation,
    XTIRRemoteInformation,
    TUYA_DISCOVERY_NEW,
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
            source=self.source,
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
        self.show_user_input(self, flow_data)

    def get_flow_data(self) -> XTFlowDataBase | None:
        return None

    async def user_interaction_callback(
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

    KEY_NAME: str = "new_ir_key_name"

    def __init__(
        self,
        source: str,
        hass: HomeAssistant,
        multi_manager: mm.MultiManager,
        device: mm.XTDevice,
        hub: XTIRHubInformation,
        remote: XTIRRemoteInformation,
    ) -> None:
        self.multi_manager = multi_manager
        self.device = device
        self.hub = hub
        self.remote = remote
        super().__init__(source, hass)

    def get_flow_data(self) -> XTFlowDataBase | None:
        return XTFlowDataAddIRDeviceKey(
            flow_id=None,
            source=self.source,
            multi_manager=self.multi_manager,
            hass=self.hass,
            schema=vol.Schema(
                {
                    vol.Required(XTDataEntryAddIRDeviceKey.KEY_NAME, default=""): str,
                }
            ),
            title=f"Add new key for {self.device.name}",
            device=self.device,
            processing_callback=None,
            hub=self.hub,
            remote=self.remote,
        )

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
            source=self.source,
            multi_manager=multi_manager,
            hass=hass,
            schema=vol.Schema(
                {
                    vol.Required(XTDataEntryAddIRDeviceKey.KEY_NAME, default=""): str,
                }
            ),
            title=f"Add new key for {device.name}",
            device=device,
            processing_callback=None,
            hub=hub,
            remote=remote,
        )
        self._fire_event(flow_data)
        # self.show_user_input(self, flow_data)

    async def user_interaction_callback(
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
            real_flow_data.key_name = discovery_info.get(
                XTDataEntryAddIRDeviceKey.KEY_NAME
            )
            if real_flow_data.key_name == "":
                real_flow_data.key_name = None
        if real_flow_data.key_name is None:
            return self.async_show_form(
                config_flow=config_flow,
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            XTDataEntryAddIRDeviceKey.KEY_NAME, default=""
                        ): str,
                    }
                ),
            )
        else:
            if await flow_data.hass.async_add_executor_job(
                flow_data.multi_manager.learn_ir_key,
                real_flow_data.device,
                real_flow_data.remote,
                real_flow_data.hub,
                real_flow_data.key_name,
            ):
                dispatcher_send(
                    flow_data.hass,
                    TUYA_DISCOVERY_NEW,
                    [real_flow_data.remote.remote_id, real_flow_data.hub.device_id],
                )
                return self.async_abort(
                    config_flow=config_flow,
                    reason=f"Key {real_flow_data.key_name} successfully added.",
                )
            else:
                return self.async_abort(
                    config_flow=config_flow,
                    reason=f"Error adding key {real_flow_data.key_name}.",
                )
        # return self.async_abort(config_flow=config_flow, reason="")
