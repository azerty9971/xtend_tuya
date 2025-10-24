from __future__ import annotations
import uuid
from abc import ABC, abstractmethod
import voluptuous as vol
from dataclasses import dataclass
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import (
    ConfigFlowContext,
    ConfigFlowResult,
    ConfigFlow,
)
from homeassistant.helpers.typing import (
    DiscoveryInfoType,
)
from ....const import (
    DOMAIN,
)
from ..threading import (
    XTEventLoopProtector,
)
import custom_components.xtend_tuya.multi_manager.multi_manager as mm


@dataclass
class XTFlowDataBase:
    flow_id: str | None
    source: str
    multi_manager: mm.MultiManager
    processing_class: XTDataEntryManager


class XTDataEntryManager(ABC):
    def __init__(self, source: str, hass: HomeAssistant) -> None:
        self.source = source
        self.hass = hass
        self.flow_data = self.get_flow_data()
        self.unique_id = self.get_unique_id()
        self.register_bus_event(hass)

    # def __del__(self):
    #    pass

    def get_unique_id(self) -> str:
        return f"{DOMAIN}_{self.source}_{uuid.uuid4()}"

    def register_bus_event(self, hass: HomeAssistant) -> str:
        @callback
        def register_event(_):
            self.show_user_input()

        hass.bus.async_listen(self.unique_id, register_event)
        return self.unique_id

    @abstractmethod
    def get_flow_data(self) -> XTFlowDataBase:
        pass

    def fire_event(self):
        self.hass.bus.fire(self.unique_id, {})

    @callback
    def show_user_input(self):
        self.flow_data.processing_class = self
        XTEventLoopProtector.execute_out_of_event_loop(
            self.hass.config_entries.flow.async_init,
            DOMAIN,
            context=ConfigFlowContext(
                source=self.source,
                title_placeholders=self.get_translation_placeholders(),
            ),
            data=self.flow_data,
        )

    def get_translation_placeholders(self) -> dict[str, str]:
        return {"name": self.source}

    @abstractmethod
    async def user_interaction_callback(
        self,
        config_flow: ConfigFlow,
        discovery_info: DiscoveryInfoType | None,
    ) -> ConfigFlowResult:
        pass

    def finish_flow(
        self,
        *,
        config_flow: ConfigFlow,
        reason: str,
    ) -> ConfigFlowResult:
        return config_flow.async_abort(
            reason=reason, description_placeholders=self.get_translation_placeholders()
        )

    def async_show_form(
        self,
        *,
        config_flow: ConfigFlow,
        data_schema: vol.Schema | None = None,
        errors: dict[str, str] | None = None,
        last_step: bool | None = None,
        preview: str | None = None,
    ) -> ConfigFlowResult:
        return config_flow.async_show_form(
            step_id=self.source,
            data_schema=data_schema,
            errors=errors,
            description_placeholders=self.get_translation_placeholders(),
            last_step=last_step,
            preview=preview,
        )
