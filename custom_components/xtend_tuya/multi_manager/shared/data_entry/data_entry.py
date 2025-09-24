from __future__ import annotations

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    discovery_flow,
)
from homeassistant.config_entries import (
    SOURCE_SYSTEM,
    SOURCE_RECONFIGURE,
    ConfigFlowContext,
)
from ....const import DOMAIN, LOGGER
import custom_components.xtend_tuya.multi_manager.multi_manager as mm


def show_test_user_input(hass: HomeAssistant, multi_manager: mm.MultiManager):
    hass.add_job(_show_test_user_input, hass, multi_manager)


async def _show_test_user_input(hass: HomeAssistant, multi_manager: mm.MultiManager):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context=ConfigFlowContext(
            source=SOURCE_SYSTEM,
            entry_id=multi_manager.config_entry.entry_id,
            title_placeholders={"name": multi_manager.config_entry.title},
            unique_id=multi_manager.config_entry.unique_id,
        ),
        data=None,
    )
    LOGGER.warning(f"Result data: {result}")
