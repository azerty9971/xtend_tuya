from __future__ import annotations

from typing import Callable, cast  # noqa: F401
from abc import ABC, abstractmethod
from collections.abc import Mapping
import voluptuous as vol
from dataclasses import dataclass
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import (
    SOURCE_DISCOVERY,
    ConfigFlowContext,
    ConfigFlowResult,
    ConfigFlow,
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

    def __init__(self, source: str) -> None:
        self.source = source

    def show_user_input(
        self, base_class: XTDataEntryManager, flow_data: XTFlowDataBase
    ):
        flow_data.processing_callback = base_class.user_interaction_callback
        flow_data.hass.add_job(self._show_user_input, flow_data)

    async def _show_user_input(self, flow_data: XTFlowDataBase):
        result = await flow_data.hass.config_entries.flow.async_init(
            DOMAIN,
            context=ConfigFlowContext(
                source=self.source,
                entry_id=flow_data.multi_manager.config_entry.entry_id,
                title_placeholders={"name": f"{flow_data.title}"},
            ),
            data=flow_data,
        )
        LOGGER.warning(f"Result data: {result}")
        flow_data.flow_id = result.get("flow_id")
        if flow_data.flow_id is not None:
            flow_data.multi_manager.register_user_input_data(flow_data)
        else:
            LOGGER.warning(
                f"Could not register flow data in multi manager (flow_id is None), title={flow_data.title}"
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
        new_schema = data_schema
        if new_schema is not None:
            new_schema = vol.Schema({vol.Required(str(self.source)): data_schema})
        return config_flow.async_show_form(
            step_id=SOURCE_DISCOVERY,
            data_schema=new_schema,
            errors=errors,
            description_placeholders=description_placeholders,
            last_step=last_step,
            preview=preview,
        )
