from __future__ import annotations

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from aiohttp import web
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
from ....util import (
    get_all_multi_managers,
)

from homeassistant.const import (
    CONF_DEVICE_ID,
)

CONF_SOURCE = "source"
CONF_STREAM_TYPE = "stream_type"
CONF_METHOD = "method"
CONF_URL = "url"
CONF_PAYLOAD = "payload"
CONF_SESSION_ID = "session_id"
CONF_FORMAT = "format"
CONF_CHANNEL = "channel"

SERVICE_GET_CAMERA_STREAM_URL = "get_camera_stream_url"
SERVICE_GET_CAMERA_STREAM_URL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Optional(CONF_SOURCE): cv.string,
        vol.Optional(CONF_STREAM_TYPE): cv.string,
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

SERVICE_GET_ICE_SERVERS = "webrtc_get_ice_servers"
SERVICE_GET_ICE_SERVERS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_SESSION_ID): cv.string,
        vol.Optional(CONF_SOURCE): cv.string,
        vol.Optional(CONF_FORMAT): cv.string,
    }
)

SERVICE_WEBRTC_SDP_EXCHANGE = "webrtc_sdp_exchange"
SERVICE_WEBRTC_SDP_EXCHANGE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_SESSION_ID): cv.string,
        vol.Optional(CONF_SOURCE): cv.string,
        vol.Optional(CONF_CHANNEL): cv.string,
    }
)

SERVICE_WEBRTC_DEBUG = "webrtc_debug"
SERVICE_WEBRTC_DEBUG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SESSION_ID): cv.string,
        vol.Optional(CONF_SOURCE): cv.string,
    }
)

class ServiceManager:
    def __init__(self, multi_manager: MultiManager) -> None:
        self.multi_manager = multi_manager
        self.hass = multi_manager.hass
        
    def register_services(self):
        self._register_service(
            DOMAIN, 
            SERVICE_GET_CAMERA_STREAM_URL, 
            self._handle_get_camera_stream_url, 
            SERVICE_GET_CAMERA_STREAM_URL_SCHEMA, 
            True, 
            True, 
            True
            )
        self._register_service(
            DOMAIN, 
            SERVICE_CALL_API, 
            self._handle_call_api, 
            SERVICE_CALL_API_SCHEMA, 
            True, 
            True, 
            True
            )
        self._register_service(
            DOMAIN, 
            SERVICE_GET_ICE_SERVERS, 
            self._handle_get_ice_servers, 
            SERVICE_GET_ICE_SERVERS_SCHEMA, 
            True, 
            True, 
            False
            )
        self._register_service(
            DOMAIN, 
            SERVICE_WEBRTC_SDP_EXCHANGE, 
            self._handle_webrtc_sdp_exchange, 
            SERVICE_WEBRTC_SDP_EXCHANGE_SCHEMA, 
            True, 
            True, 
            False
            )
        self._register_service(
            DOMAIN, 
            SERVICE_WEBRTC_DEBUG, 
            self._handle_webrtc_debug, 
            SERVICE_WEBRTC_DEBUG_SCHEMA, 
            True, 
            True, 
            False
            )

    def _register_service(self, domain: str, name: str, callback, schema, requires_auth: bool = True, allow_from_api:bool = True, use_cache:bool = True):
        self.hass.services.async_register(
            domain, name, callback, schema=schema
        )
        if allow_from_api:
            self.hass.http.register_view(XTGeneralView(name, callback, requires_auth, use_cache))
    
    def _get_correct_multi_manager(self, source: str, device_id: str) -> MultiManager | None:
        multi_manager_list = get_all_multi_managers(self.hass)
        for multi_manager in multi_manager_list:
            if account := multi_manager.get_account_by_name(source):
                if account.get_devices_from_device_id(device_id):
                    return multi_manager
        return None
    
    async def _handle_get_camera_stream_url(self, event: XTEventData) -> web.Response | str | None:
        source      = event.data.get(CONF_SOURCE, MESSAGE_SOURCE_TUYA_SHARING)
        device_id   = event.data.get(CONF_DEVICE_ID, None)
        stream_type = event.data.get(CONF_STREAM_TYPE, "rtsp")
        if not source or not device_id:
            return None
        if multi_manager := self._get_correct_multi_manager(source, device_id):
            if account := multi_manager.get_account_by_name(source):
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
        session_id  = event.data.get(CONF_SESSION_ID, None)
        format      = event.data.get(CONF_FORMAT, "GO2RTC")
        if device_id is None or session_id is None:
            return None
        if multi_manager := self._get_correct_multi_manager(source, device_id):
            if account := multi_manager.get_account_by_name(source):
                if ice_servers := await self.hass.async_add_executor_job(account.get_webrtc_ice_servers, device_id, session_id, format):
                    return ice_servers
        return None


    async def _handle_webrtc_debug(self, event: XTEventData) -> web.Response | str | None:
        source      = event.data.get(CONF_SOURCE, MESSAGE_SOURCE_TUYA_IOT)
        session_id  = event.data.get(CONF_SESSION_ID, None)
        #LOGGER.warning(f"DEBUG CALL: {event}")
        if session_id is None:
            return None
        multi_manager_list = get_all_multi_managers(self.hass)
        for multi_manager in multi_manager_list:
            if account := multi_manager.get_account_by_name(source):
                if debug_output := await self.hass.async_add_executor_job(account.get_webrtc_exchange_debug, session_id):
                    #LOGGER.warning(f"DEBUG OUTPUT: {debug_output}")
                    return debug_output
        return None

    async def _handle_webrtc_sdp_exchange(self, event: XTEventData) -> web.Response | str | None:
        source      = event.data.get(CONF_SOURCE, MESSAGE_SOURCE_TUYA_IOT)
        device_id   = event.data.get(CONF_DEVICE_ID, None)
        session_id  = event.data.get(CONF_SESSION_ID, None)
        channel     = event.data.get(CONF_CHANNEL, None)
        #LOGGER.warning(f"DEBUG SDP CALL: {event}")
        if device_id is None or session_id is None:
            return None
        multi_manager = self._get_correct_multi_manager(source, device_id)
        if multi_manager is None:
            return None
        match event.method:
            case "POST":
                match event.content_type:
                    case "application/sdp":
                        if account := multi_manager.get_account_by_name(source):
                            sdp_answer = await self.hass.async_add_executor_job(account.get_webrtc_sdp_answer, device_id, session_id, event.payload, channel)
                            if sdp_answer is not None:
                                response = web.Response(status=201, text=sdp_answer, content_type="application/sdp", charset="utf-8")
                                response.headers["ETag"] = session_id
                                response.headers["Location"] = event.location
                                response.headers["Accept-Patch"] = "application/trickle-ice-sdpfrag"
                                return response
                        return None
            case "PATCH":
                match event.content_type:
                    case "application/trickle-ice-sdpfrag":
                        if account := multi_manager.get_account_by_name(source):
                            patch_answer = await self.hass.async_add_executor_job(account.send_webrtc_trickle_ice, device_id, session_id, event.payload)
                            if patch_answer is not None:
                                response = web.Response(status=200, text=patch_answer, charset="utf-8")
                                response.headers["ETag"] = session_id
                                return response
                        return None
            case "DELETE":
                if account := multi_manager.get_account_by_name(source):
                    delete_answer = await self.hass.async_add_executor_job(account.delete_webrtc_session, device_id, session_id)
                    if delete_answer is not None:
                        response = web.Response(status=200, text=delete_answer, charset="utf-8")
                        return response
                return None
