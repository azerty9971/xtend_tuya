from __future__ import annotations
import uuid
from typing import Callable, cast  # noqa: F401
from abc import ABC, abstractmethod
from collections.abc import Mapping
import voluptuous as vol
from dataclasses import dataclass
from homeassistant.core import HomeAssistant, callback, Event
from homeassistant.config_entries import (
    ConfigFlowContext,
    ConfigFlowResult,
    ConfigFlow,
    SOURCE_USER
)
from homeassistant.helpers.typing import (
    DiscoveryInfoType,
)
from ....const import DOMAIN, LOGGER
import custom_components.xtend_tuya.multi_manager.multi_manager as mm


@dataclass
class XTFlowDataBase:
    flow_id: str | None
    source: str
    multi_manager: mm.MultiManager
    hass: HomeAssistant
    schema: vol.Schema
    title: str
    processing_callback: Callable | None


class XTDataEntryManager(ABC):

    def __init__(self, source: str, hass: HomeAssistant) -> None:
        self.source = source
        self.hass = hass
        self.event_id = self.register_bus_event(hass)
        self.flow_data = self.get_flow_data()
#    def __del__(self):
#        pass

    def register_bus_event(self, hass: HomeAssistant) -> str:
        listen_id = f"{DOMAIN}_{uuid.uuid4()}"
        @callback
        def register_event(event):
            LOGGER.warning(f"Called registered event: {type(event)}")
            if flow_data := self.get_flow_data():
                self.show_user_input(self, flow_data)
        hass.bus.async_listen(listen_id, register_event)
        return listen_id
    

    @abstractmethod
    def get_flow_data(self) -> XTFlowDataBase | None:
        pass

    def fire_event(self):
        #if flow_data := self.get_flow_data():
        #    self._fire_event(flow_data)
        self.hass.bus.fire(self.event_id, {})

    #@callback
    #def _fire_event(self, flow_data: XTFlowDataBase):
    #    self.hass.bus.fire(self.event_id, {})

    @callback
    def show_user_input(
        self, base_class: XTDataEntryManager, flow_data: XTFlowDataBase
    ):
        flow_data.processing_callback = base_class.user_interaction_callback
        flow_data.hass.add_job(self._show_user_input)

    async def _show_user_input(self):
        if self.flow_data is None:
            LOGGER.warning(f"Flow data is empty {self.event_id}")
            return
        result = await self.hass.config_entries.flow.async_init(
            DOMAIN,
            context=ConfigFlowContext(
                source=SOURCE_USER,
                # entry_id=flow_data.multi_manager.config_entry.entry_id,
                #title_placeholders={"name": f"{flow_data.title}"},
            ),
            data=self.flow_data,
        )
        LOGGER.warning(f"Result data: {result}")
        self.flow_data.flow_id = result.get("flow_id")
        if self.flow_data.flow_id is not None:
            self.flow_data.multi_manager.register_user_input_data(self.flow_data)
        else:
            LOGGER.warning(
                f"Could not register flow data in multi manager (flow_id is None), title={self.flow_data.title}"
            )

    @abstractmethod
    async def user_interaction_callback(
        self,
        config_flow: ConfigFlow,
        flow_data: XTFlowDataBase,
        discovery_info: DiscoveryInfoType | None,
    ) -> ConfigFlowResult:
        pass

    def async_abort(
        self,
        *,
        config_flow: ConfigFlow,
        reason: str,
        description_placeholders: Mapping[str, str] | None = None,
    ) -> ConfigFlowResult:
        return config_flow.async_abort(
            reason=reason, description_placeholders=description_placeholders
        )

    def async_show_form(
        self,
        *,
        config_flow: ConfigFlow,
        data_schema: vol.Schema | None = None,
        errors: dict[str, str] | None = None,
        description_placeholders: Mapping[str, str] | None = None,
        last_step: bool | None = None,
        preview: str | None = None,
    ) -> ConfigFlowResult:
        return config_flow.async_show_form(
            step_id=self.source,
            data_schema=data_schema,
            errors=errors,
            description_placeholders=description_placeholders,
            last_step=last_step,
            preview=preview,
        )
