from __future__ import annotations

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from aiohttp import web
import json

from ...multi_manager import (
    MultiManager,
)

from .views import (
    XTGeneralView,
    XTEventData,
)

from ....const import (
    DOMAIN,
    LOGGER,  # noqa: F401
    MESSAGE_SOURCE_TUYA_SHARING,
    MESSAGE_SOURCE_TUYA_IOT,
)

from homeassistant.const import (
    CONF_DEVICE_ID,
)

CONF_SOURCE = "source"
CONF_STREAM_TYPE = "stream_type"
CONF_METHOD = "method"
CONF_URL = "url"
CONF_PAYLOAD = "payload"
CONF_USE_CACHE = "use_cache"

SERVICE_GET_CAMERA_STREAM_URL = "get_camera_stream_url"
SERVICE_GET_CAMERA_STREAM_URL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Optional(CONF_SOURCE): cv.string,
        vol.Optional(CONF_STREAM_TYPE): cv.string,
        vol.Optional(CONF_USE_CACHE): cv.string,
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

SERVICE_GET_ICE_SERVERS = "get_ice_servers"
SERVICE_GET_ICE_SERVERS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_SOURCE): cv.string,
    }
)

SERVICE_WEBRTC = "webrtc"
SERVICE_GET_CAMERA_STREAM_URL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_SOURCE): cv.string,
    }
)

class ServiceManager:
    def __init__(self, multi_manager: MultiManager) -> None:
        self.multi_manager = multi_manager
        self.hass = multi_manager.hass
        
    def register_services(self):
        self._register_service(DOMAIN, SERVICE_GET_CAMERA_STREAM_URL, self._handle_get_camera_stream_url, SERVICE_GET_CAMERA_STREAM_URL_SCHEMA, True, True, True)
        self._register_service(DOMAIN, SERVICE_CALL_API, self._handle_call_api, SERVICE_CALL_API_SCHEMA, True, True, True)
        self._register_service(DOMAIN, SERVICE_GET_ICE_SERVERS, self._handle_get_ice_servers, SERVICE_GET_ICE_SERVERS_SCHEMA, True, True, False)
        self._register_service(DOMAIN, SERVICE_WEBRTC, self._handle_webrtc, SERVICE_GET_CAMERA_STREAM_URL_SCHEMA, False, True, False)

    def _register_service(self, domain: str, name: str, callback, schema, requires_auth: bool = True, allow_from_api:bool = True, use_cache:bool = True):
        self.hass.services.async_register(
            domain, name, callback, schema=schema
        )
        if allow_from_api:
            self.hass.http.register_view(XTGeneralView(name, callback, requires_auth, use_cache))
    
    async def _handle_get_camera_stream_url(self, event: XTEventData) -> web.Response | str | None:
        source      = event.data.get(CONF_SOURCE, MESSAGE_SOURCE_TUYA_SHARING)
        device_id   = event.data.get(CONF_DEVICE_ID, None)
        stream_type = event.data.get(CONF_STREAM_TYPE, "rtsp")
        if not source or not device_id:
            return None
        if account := self.multi_manager.get_account_by_name(source):
            response = await self.hass.async_add_executor_job(account.get_device_stream_allocate, device_id, stream_type)
            return response
        return None
    
    async def _handle_call_api(self, event: XTEventData) -> web.Response | str | None:
        source  = event.data.get(CONF_SOURCE, None)
        method  = event.data.get(CONF_METHOD, None)
        url     = event.data.get(CONF_URL, None)
        payload = event.data.get(CONF_PAYLOAD, None)
        if account := self.multi_manager.get_account_by_name(source):
            try:
                if response := await self.hass.async_add_executor_job(account.call_api, method, url, payload):
                    LOGGER.warning(f"API call response: {response}")
                    return response
            except Exception as e:
                LOGGER.warning(f"API Call failed: {e}")
    
    async def _handle_get_ice_servers(self, event: XTEventData) -> web.Response | str | None:
        source      = event.data.get(CONF_SOURCE, MESSAGE_SOURCE_TUYA_IOT)
        device_id   = event.data.get(CONF_DEVICE_ID, None)
        api_event_data: XTEventData = XTEventData()
        api_event_data.query_params[CONF_SOURCE] = source
        api_event_data.query_params[CONF_METHOD] = "GET"
        api_event_data.query_params[CONF_URL]    = f"/v1.0/devices/{device_id}/webrtc-configs"
        if api_reponse := await self._handle_call_api(api_event_data):
            if api_reponse.get("success"):
                result = api_reponse.get("result", {})
                p2p_config = result.get("p2p_config", {})
                if ices := p2p_config.get("ices"):
                    return json.dumps(ices).replace(': ', ':').replace(', ', ',')


    async def _handle_webrtc(self, event: XTEventData) -> web.Response | str | None:
        LOGGER.warning(f"_handle_webrtc: {event}")
        source      = event.data.get(CONF_SOURCE, MESSAGE_SOURCE_TUYA_IOT)
        device_id   = event.data.get(CONF_DEVICE_ID, None)
        session_id  = event.session_id
        if not device_id:
            return None
        match event.method:
            case "POST":
                match event.content_type:
                    case "application/sdp":
                        if account := self.multi_manager.get_account_by_name(source):
                            if sdp_answer := await self.hass.async_add_executor_job(account.get_sdp_answer, device_id, session_id, event.payload):
                                LOGGER.warning(f"Got SDP answer: {sdp_answer}")
                                return web.Response(status=201, body=sdp_answer, content_type="application/sdp")
                        return None
