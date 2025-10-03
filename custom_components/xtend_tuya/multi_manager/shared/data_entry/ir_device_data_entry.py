from __future__ import annotations

import voluptuous as vol
from typing import cast
from dataclasses import dataclass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import dispatcher_send
from .shared_data_entry import (
    XTFlowDataBase,
    XTDataEntryManager,
    ConfigFlow,
    ConfigFlowResult,
    DiscoveryInfoType,
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
    hub: XTIRHubInformation
    step: int = 1


@dataclass
class XTFlowDataAddIRDeviceKey(XTFlowDataBase):
    device: mm.XTDevice
    hub: XTIRHubInformation
    remote: XTIRRemoteInformation
    key_name: str | None = None


class XTDataEntryAddIRDevice(XTDataEntryManager):

    def __init__(
        self,
        source: str,
        hass: HomeAssistant,
        multi_manager: mm.MultiManager,
        device: mm.XTDevice,
        hub: XTIRHubInformation,
    ) -> None:
        self.multi_manager = multi_manager
        self.device = device
        self.hub = hub
        super().__init__(source, hass)
    
    def get_translation_placeholders(self) -> dict[str, str]:
        return super().get_translation_placeholders() | {
            "device_name": self.device.name,
            "name": f"Add IR device under {self.device.name}"
        }

    def get_flow_data(self) -> XTFlowDataBase:
        return XTFlowDataAddIRDevice(
            flow_id=None,
            source=self.source,
            multi_manager=self.multi_manager,
            device=self.device,
            processing_class=self,
            hub=self.hub,
        )

    async def user_interaction_callback(
        self,
        config_flow: ConfigFlow,
        discovery_info: DiscoveryInfoType | None,
    ) -> ConfigFlowResult:
        LOGGER.warning(
            f"Calling XTDataEntryAddIRDevice->user_interaction_callback: flow_data: {self.flow_data}, discovery_info: {discovery_info}"
        )

        return self.finish_flow(config_flow=config_flow, reason="")


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
        self.flow_data = cast(XTFlowDataAddIRDeviceKey, self.flow_data)

    def get_translation_placeholders(self) -> dict[str, str]:
        return super().get_translation_placeholders() | {
            "key_name": (
                self.flow_data.key_name if self.flow_data.key_name is not None else ""
            ),
            "device_name": self.flow_data.device.name,
            "name": f"Add IR Key for {self.device.name}"
        }

    def get_flow_data(self) -> XTFlowDataBase:
        return XTFlowDataAddIRDeviceKey(
            flow_id=None,
            source=self.source,
            multi_manager=self.multi_manager,
            device=self.device,
            processing_class=self,
            hub=self.hub,
            remote=self.remote,
        )

    async def user_interaction_callback(
        self,
        config_flow: ConfigFlow,
        discovery_info: DiscoveryInfoType | None,
    ) -> ConfigFlowResult:
        if discovery_info is not None:
            self.flow_data.key_name = discovery_info.get(
                XTDataEntryAddIRDeviceKey.KEY_NAME
            )
            if self.flow_data.key_name == "":
                self.flow_data.key_name = None
        if self.flow_data.key_name is None:
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
            if await self.hass.async_add_executor_job(
                self.flow_data.multi_manager.learn_ir_key,
                self.flow_data.device,
                self.flow_data.remote,
                self.flow_data.hub,
                self.flow_data.key_name,
            ):
                dispatcher_send(
                    self.hass,
                    TUYA_DISCOVERY_NEW,
                    [self.flow_data.remote.remote_id, self.flow_data.hub.device_id],
                )
                return self.finish_flow(
                    config_flow=config_flow, reason="ir_add_key_success"
                )
            else:
                return self.finish_flow(
                    config_flow=config_flow, reason="ir_add_key_failed"
                )
