from __future__ import annotations

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from .multi_manager.multi_manager import (
    MultiManager,
)

from .const import (
    DOMAIN,
    LOGGER,  # noqa: F401
)

from homeassistant.const import (
    CONF_DEVICE_ID,
)

CONF_SOURCE = "source"

SERVICE_GET_CAMERA_STREAM_URL = "get_camera_stream_url"
SERVICE_GET_CAMERA_STREAM_URL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Optional(CONF_SOURCE): cv.string,
    }
)

class ServiceManager:
    def __init__(self, multi_manager: MultiManager) -> None:
        self.multi_manager = multi_manager
        self.hass = multi_manager.hass
        
    def register_services(self):
        self.hass.services.async_register(
            DOMAIN, SERVICE_GET_CAMERA_STREAM_URL, self._handle_get_camera_stream_url, schema=SERVICE_GET_CAMERA_STREAM_URL_SCHEMA
        )
    
    async def _handle_get_camera_stream_url(self, event):
        LOGGER.warning(f"_handle_get_camera_stream_url: {event}")

    