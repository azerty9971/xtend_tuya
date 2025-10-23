from __future__ import annotations

import voluptuous as vol
from typing import cast
from enum import StrEnum
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
from ..threading import (
    XTEventLoopProtector,
)
import custom_components.xtend_tuya.multi_manager.multi_manager as mm


@dataclass
class XTFlowDataAddIRDevice(XTFlowDataBase):
    hub_device: mm.XTDevice
    hub: XTIRHubInformation
    step: int = 1
    device_name: str | None = None
    device_category: int | None = None
    device_category_dict: dict[int, str] | None = None
    device_brand_id: int | None = None
    device_brand_name: str | None = None
    device_brand_dict: dict[int, str] | None = None

    def __repr__(self) -> str:
        return f"hub_device: {self.hub_device.name if self.hub_device is not None else "None"}, step: {self.step}, device_name: {self.device_name}, device_category: {self.device_category}, device_category_dict: {self.device_category_dict}, device_brand_id: {self.device_brand_id}, device_brand_name: {self.device_brand_name}, device_brand_dict: {self.device_brand_dict}"


@dataclass
class XTFlowDataAddIRDeviceKey(XTFlowDataBase):
    device: mm.XTDevice
    hub: XTIRHubInformation
    remote: XTIRRemoteInformation
    key_name: str | None = None


class XTDataEntryAddIRDevice(XTDataEntryManager):
    class Fields(StrEnum):
        DEVICE_NAME = "device_name"
        DEVICE_CATEGORY = "device_category"
        DEVICE_BRAND_ID = "device_brand_id"
        DEVICE_BRAND_NAME = "device_brand_name"

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
        self.flow_data = cast(XTFlowDataAddIRDevice, self.flow_data)

    def get_translation_placeholders(self) -> dict[str, str]:
        return super().get_translation_placeholders() | {
            "remote_name": (
                self.flow_data.device_name
                if self.flow_data.device_name is not None
                else ""
            ),
            "device_name": self.device.name,
            "name": f"Add IR device under {self.device.name}",
        }

    def get_flow_data(self) -> XTFlowDataBase:
        return XTFlowDataAddIRDevice(
            flow_id=None,
            source=self.source,
            multi_manager=self.multi_manager,
            hub_device=self.device,
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
        match self.flow_data.step:
            case 1:
                if discovery_info is not None:
                    self.flow_data.device_name = discovery_info.get(
                        XTDataEntryAddIRDevice.Fields.DEVICE_NAME
                    )
                    if self.flow_data.device_name == "":
                        self.flow_data.device_name = None
                else:
                    return self.async_show_form(
                        config_flow=config_flow,
                        data_schema=vol.Schema(
                            {
                                vol.Required(
                                    str(XTDataEntryAddIRDevice.Fields.DEVICE_NAME),
                                    default="",
                                ): str,
                            }
                        ),
                    )
                if self.flow_data.device_name is not None:
                    self.flow_data.step = 2
                    self.flow_data.device_category_dict = (
                        await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                            self.flow_data.multi_manager.get_ir_category_list,
                            self.flow_data.hub_device,
                        )
                    )
                    return await self.user_interaction_callback(config_flow, None)
            case 2:
                if discovery_info is not None:
                    self.flow_data.device_category = discovery_info.get(
                        XTDataEntryAddIRDevice.Fields.DEVICE_CATEGORY
                    )
                    if self.flow_data.device_category == 0:
                        self.flow_data.device_category = None
                else:
                    if self.flow_data.device_category_dict is None:
                        LOGGER.error(
                            f"Infrared category list for device {self.flow_data.hub_device.name} was not retrieved"
                        )
                        return self.finish_flow(config_flow=config_flow, reason="")
                    return self.async_show_form(
                        config_flow=config_flow,
                        data_schema=vol.Schema(
                            {
                                vol.Required(
                                    str(XTDataEntryAddIRDevice.Fields.DEVICE_CATEGORY)
                                ): vol.In(
                                    {
                                        key: value
                                        for key, value in self.flow_data.device_category_dict.items()
                                    }
                                )
                            }
                        ),
                    )
                if self.flow_data.device_category is not None:
                    self.flow_data.step = 3
                    self.flow_data.device_brand_dict = (
                        await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                            self.flow_data.multi_manager.get_ir_brand_list,
                            self.flow_data.hub_device,
                            self.flow_data.device_category,
                        )
                    )
                    return await self.user_interaction_callback(config_flow, None)
            case 3:
                if discovery_info is not None:
                    self.flow_data.device_brand_id = discovery_info.get(
                        XTDataEntryAddIRDevice.Fields.DEVICE_BRAND_ID
                    )
                    if (
                        self.flow_data.device_brand_id is not None
                        and self.flow_data.device_brand_dict is not None
                    ):
                        self.flow_data.device_brand_name = (
                            self.flow_data.device_brand_dict[
                                self.flow_data.device_brand_id
                            ]
                        )
                else:
                    if self.flow_data.device_brand_dict is None:
                        LOGGER.error(
                            f"Infrared brand list (for category {self.flow_data.device_category}) for device {self.flow_data.hub_device.name} was not retrieved"
                        )
                        return self.finish_flow(config_flow=config_flow, reason="")
                    if len(self.flow_data.device_brand_dict) == 0:
                        # This category doesn't have brand support, skip this step
                        self.flow_data.step = 4
                        self.flow_data.device_brand_id = 999999
                        self.flow_data.device_brand_name = "Other"
                        return await self.user_interaction_callback(config_flow, None)
                    return self.async_show_form(
                        config_flow=config_flow,
                        data_schema=vol.Schema(
                            {
                                vol.Required(
                                    str(XTDataEntryAddIRDevice.Fields.DEVICE_BRAND_ID)
                                ): vol.In(
                                    {
                                        key: value
                                        for key, value in self.flow_data.device_brand_dict.items()
                                    }
                                )
                            }
                        ),
                    )
                if self.flow_data.device_brand_id is not None:
                    self.flow_data.step = 4
                    return await self.user_interaction_callback(config_flow, None)
            case 4:
                # We have all the information to create the device
                new_device_id = (
                    await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                        self.flow_data.multi_manager.create_ir_device,
                        self.flow_data.hub_device,
                        self.flow_data.device_name,
                        self.flow_data.device_category,
                        self.flow_data.device_brand_id,
                        self.flow_data.device_brand_name,
                    )
                )
                if new_device_id is not None:
                    await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                        self.multi_manager.add_device_by_id, new_device_id
                    )
                    dispatcher_send(
                        self.hass,
                        TUYA_DISCOVERY_NEW,
                        [new_device_id, self.flow_data.hub.device_id],
                    )
                    return self.finish_flow(
                        config_flow=config_flow, reason="ir_add_device_success"
                    )
        return self.finish_flow(config_flow=config_flow, reason="ir_add_device_failed")


class XTDataEntryAddIRDeviceKey(XTDataEntryManager):
    class Fields(StrEnum):
        KEY_NAME = "new_ir_key_name"

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
            "name": f"Add IR Key for {self.device.name}",
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
                XTDataEntryAddIRDeviceKey.Fields.KEY_NAME
            )
            if self.flow_data.key_name == "":
                self.flow_data.key_name = None
        if self.flow_data.key_name is None:
            return self.async_show_form(
                config_flow=config_flow,
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            XTDataEntryAddIRDeviceKey.Fields.KEY_NAME, default=""
                        ): str,
                    }
                ),
            )
        else:
            if await XTEventLoopProtector.execute_out_of_event_loop_and_return(
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
