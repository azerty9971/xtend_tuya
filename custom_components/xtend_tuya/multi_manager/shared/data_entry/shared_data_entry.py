from __future__ import annotations
import uuid
from typing import Callable, cast  # noqa: F401
from abc import ABC, abstractmethod
from collections.abc import Mapping
import voluptuous as vol
from dataclasses import dataclass
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import (
    ConfigFlowContext,
    ConfigFlowResult,
    ConfigFlow,
    SOURCE_DISCOVERY,
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
    processing_class: XTDataEntryManager


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
        def register_event(_):
            self.show_user_input()

        hass.bus.async_listen(listen_id, register_event)
        return listen_id

    @abstractmethod
    def get_flow_data(self) -> XTFlowDataBase:
        pass

    def fire_event(self):
        # if flow_data := self.get_flow_data():
        #    self._fire_event(flow_data)
        LOGGER.warning(f"Firing event {self.event_id}")
        self.hass.bus.fire(self.event_id, {})

    # @callback
    # def _fire_event(self, flow_data: XTFlowDataBase):
    #    self.hass.bus.fire(self.event_id, {})

    @callback
    def show_user_input(self):
        self.flow_data.processing_class = self
        self.hass.async_create_task(
            self.hass.config_entries.flow.async_init(
                DOMAIN,
                context=ConfigFlowContext(
                    source=SOURCE_DISCOVERY,
                    unique_id=f"{DOMAIN}_{uuid.uuid4()}",
                    # title_placeholders={"name": f"{flow_data.title}"},
                ),
                data=self.flow_data,
            )
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
