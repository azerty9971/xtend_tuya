from __future__ import annotations

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from ...multi_manager import (
    MultiManager,
)

from .views import (
    XTGeneralView,
)

from ....const import (
    DOMAIN,
    LOGGER,  # noqa: F401
)

from homeassistant.const import (
    CONF_DEVICE_ID,
)

CONF_SOURCE = "source"
CONF_METHOD = "method"
CONF_URL = "url"
CONF_PAYLOAD = "payload"

SERVICE_GET_CAMERA_STREAM_URL = "get_camera_stream_url"
SERVICE_GET_CAMERA_STREAM_URL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Optional(CONF_SOURCE): cv.string,
    }
)

SERVICE_CALL_API = "call_api"
SERVICE_CALL_API_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SOURCE): cv.string,
        vol.Required(CONF_METHOD): cv.string,
        vol.Required(CONF_URL): cv.string,
        vol.Optional(CONF_PAYLOAD): cv.string,
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
        self.hass.http.register_view(XTGeneralView(SERVICE_GET_CAMERA_STREAM_URL, self._handle_get_camera_stream_url, True))

        self.hass.services.async_register(
            DOMAIN, SERVICE_CALL_API, self._handle_call_api, schema=SERVICE_CALL_API_SCHEMA
        )
        self.hass.http.register_view(XTGeneralView(SERVICE_CALL_API, self._handle_call_api, True))
    
    async def _handle_get_camera_stream_url(self, event):
        LOGGER.warning(f"_handle_get_camera_stream_url: {event}")
        source    = event.data.get(CONF_SOURCE, None)
        device_id = event.data.get(CONF_DEVICE_ID, None)
        LOGGER.warning(f"Source: {source}, device_id: {device_id}")
        if not source or not device_id:
            return None
        if account := self.multi_manager.get_account_by_name(source):
            LOGGER.warning("Account found")
            response = account.get_device_stream_allocate(device_id, "rtsp")
            LOGGER.warning(f"Resoonse: {response}")
            return response
        return None
    
    async def _handle_call_api(self, event):
        source  = event.data.get(CONF_SOURCE, None)
        method  = event.data.get(CONF_METHOD, None)
        url     = event.data.get(CONF_URL, None)
        payload = event.data.get(CONF_PAYLOAD, None)
        LOGGER.warning(f"_handle_call_api: {source} <=> {method} <=> {url} <=> {payload}")
        if account := self.multi_manager.get_account_by_name(source):
            try:
                if response := await self.hass.async_add_executor_job(account.call_api, method, url, payload):
                    LOGGER.warning(f"API call response: {response}")
            except Exception as e:
                LOGGER.warning(f"API Call failed: {e}")

    