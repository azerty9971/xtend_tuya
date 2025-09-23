from __future__ import annotations

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    discovery_flow,
)
from homeassistant.config_entries import SOURCE_SYSTEM
from ....const import DOMAIN


def show_test_user_input(hass: HomeAssistant):
    hass.add_job(_show_test_user_input, hass)


@callback
def _show_test_user_input(hass: HomeAssistant):
    discovery_flow.async_create_flow(
        hass, DOMAIN, context={"source": SOURCE_SYSTEM}, data=None
    )
