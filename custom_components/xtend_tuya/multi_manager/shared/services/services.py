from __future__ import annotations
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from aiohttp import web
from typing import Any
import custom_components.xtend_tuya.multi_manager.multi_manager as mm
from .views import (
    XTGeneralView,
    XTEventData,
)
from ....const import (
    DOMAIN,
    LOGGER,
    MESSAGE_SOURCE_TUYA_SHARING,
    MESSAGE_SOURCE_TUYA_IOT,
)
from ..threading import (
    XTEventLoopProtector,
)
from ....util import (
    get_all_multi_managers,
)
from homeassistant.const import (
    CONF_DEVICE_ID,
)
from homeassistant.core import SupportsResponse

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

SERVICE_FDM5KW_SET_TIMER = "fdm5kw_set_timer"
SERVICE_FDM5KW_SET_TIMER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required("slot"): vol.All(cv.positive_int, vol.Range(min=0, max=6)),
        vol.Required("hour"): vol.All(cv.positive_int, vol.Range(min=0, max=23)),
        vol.Required("minute"): vol.All(cv.positive_int, vol.Range(min=0, max=59)),
        vol.Required("mode"): vol.In(["duration", "volume"]),
        vol.Required("value"): cv.positive_int,
        vol.Optional("days"): vol.Any([cv.string], cv.positive_int),
        vol.Optional("enabled", default=True): cv.boolean,
    }
)

SERVICE_FDM5KW_DELETE_TIMER = "fdm5kw_delete_timer"
SERVICE_FDM5KW_DELETE_TIMER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required("slot"): vol.All(cv.positive_int, vol.Range(min=0, max=6)),
        vol.Optional("hour"): vol.All(cv.positive_int, vol.Range(min=0, max=23)),
        vol.Optional("minute"): vol.All(cv.positive_int, vol.Range(min=0, max=59)),
        vol.Optional("days"): vol.Any([cv.string], cv.positive_int),
    }
)

SERVICE_FDM5KW_START_WATERING = "fdm5kw_start_watering"
SERVICE_FDM5KW_START_WATERING_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required("mode"): vol.In(["duration", "volume"]),
        vol.Required("value"): cv.positive_int,
    }
)

SERVICE_FDM5KW_STOP_WATERING = "fdm5kw_stop_watering"
SERVICE_FDM5KW_STOP_WATERING_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
    }
)

SERVICE_FDM5KW_CLEAR_QUOTA_LOCKOUT = "fdm5kw_clear_quota_lockout"
SERVICE_FDM5KW_CLEAR_QUOTA_LOCKOUT_SCHEMA = vol.Schema({})

SERVICE_FDM5KW_RESYNC_TIMERS = "fdm5kw_resync_timers"
SERVICE_FDM5KW_RESYNC_TIMERS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
    }
)


class ServiceManager:
    def __init__(self, multi_manager: mm.MultiManager) -> None:
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
            True,
        )
        self._register_service(
            DOMAIN,
            SERVICE_CALL_API,
            self._handle_call_api,
            SERVICE_CALL_API_SCHEMA,
            True,
            True,
            True,
        )
        self._register_service(
            DOMAIN,
            SERVICE_GET_ICE_SERVERS,
            self._handle_get_ice_servers,
            SERVICE_GET_ICE_SERVERS_SCHEMA,
            True,
            True,
            False,
        )
        self._register_service(
            DOMAIN,
            SERVICE_WEBRTC_SDP_EXCHANGE,
            self._handle_webrtc_sdp_exchange,
            SERVICE_WEBRTC_SDP_EXCHANGE_SCHEMA,
            True,
            True,
            False,
        )
        self._register_service(
            DOMAIN,
            SERVICE_WEBRTC_DEBUG,
            self._handle_webrtc_debug,
            SERVICE_WEBRTC_DEBUG_SCHEMA,
            True,
            True,
            False,
        )
        self._register_service(
            DOMAIN,
            SERVICE_FDM5KW_SET_TIMER,
            self._handle_fdm5kw_set_timer,
            SERVICE_FDM5KW_SET_TIMER_SCHEMA,
            True,
            True,
            False,
        )
        self._register_service(
            DOMAIN,
            SERVICE_FDM5KW_DELETE_TIMER,
            self._handle_fdm5kw_delete_timer,
            SERVICE_FDM5KW_DELETE_TIMER_SCHEMA,
            True,
            True,
            False,
        )
        self._register_service(
            DOMAIN,
            SERVICE_FDM5KW_START_WATERING,
            self._handle_fdm5kw_start_watering,
            SERVICE_FDM5KW_START_WATERING_SCHEMA,
            True,
            True,
            False,
        )
        self._register_service(
            DOMAIN,
            SERVICE_FDM5KW_STOP_WATERING,
            self._handle_fdm5kw_stop_watering,
            SERVICE_FDM5KW_STOP_WATERING_SCHEMA,
            True,
            True,
            False,
        )
        self._register_service(
            DOMAIN,
            SERVICE_FDM5KW_CLEAR_QUOTA_LOCKOUT,
            self._handle_fdm5kw_clear_quota_lockout,
            SERVICE_FDM5KW_CLEAR_QUOTA_LOCKOUT_SCHEMA,
            True,
            True,
            False,
        )
        self._register_service(
            DOMAIN,
            SERVICE_FDM5KW_RESYNC_TIMERS,
            self._handle_fdm5kw_resync_timers,
            SERVICE_FDM5KW_RESYNC_TIMERS_SCHEMA,
            True,
            True,
            False,
            # Returns per-valve reconcile counts so the dashboard button can
            # report "cleared N / all clean" instead of a blind fire.
            supports_response=SupportsResponse.OPTIONAL,
        )

    def _register_service(
        self,
        domain: str,
        name: str,
        callback,
        schema,
        requires_auth: bool = True,
        allow_from_api: bool = True,
        use_cache: bool = True,
        supports_response: SupportsResponse = SupportsResponse.NONE,
    ):
        self.hass.services.async_register(
            domain, name, callback, schema=schema, supports_response=supports_response
        )
        if allow_from_api:
            self.hass.http.register_view(
                XTGeneralView(name, callback, requires_auth, use_cache)
            )

    def _get_correct_multi_manager(
        self, source: str, device_id: str
    ) -> mm.MultiManager | None:
        multi_manager_list = get_all_multi_managers(self.hass)
        for multi_manager in multi_manager_list:
            if multi_manager.device_map.get(device_id):
                return multi_manager
        return None

    async def _handle_get_camera_stream_url(
        self, event: XTEventData
    ) -> web.Response | str | None:
        source = event.data.get(CONF_SOURCE, MESSAGE_SOURCE_TUYA_SHARING)
        device_id = event.data.get(CONF_DEVICE_ID, None)
        stream_type = event.data.get(CONF_STREAM_TYPE, "rtsp")
        if not source or not device_id:
            return None
        if multi_manager := self._get_correct_multi_manager(source, device_id):
            if account := multi_manager.get_account_by_name(source):
                response = (
                    await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                        account.get_device_stream_allocate, device_id, stream_type
                    )
                )
                return response
        return None

    async def _handle_call_api(
        self, event: XTEventData
    ) -> web.Response | dict[str, Any] | None:
        source = event.data.get(CONF_SOURCE, None)
        method = event.data.get(CONF_METHOD, None)
        url = event.data.get(CONF_URL, None)
        payload = event.data.get(CONF_PAYLOAD, "")
        if source is not None and method is not None and url is not None:
            if account := self.multi_manager.get_account_by_name(source):
                try:
                    if (
                        response
                        := await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                            account.call_api, method, url, payload
                        )
                    ):
                        LOGGER.debug(f"API call response: {response}")
                        return response
                except Exception as e:
                    LOGGER.warning(f"API Call failed: {e}")

    async def _handle_get_ice_servers(
        self, event: XTEventData
    ) -> web.Response | str | None:
        source = event.data.get(CONF_SOURCE, MESSAGE_SOURCE_TUYA_IOT)
        device_id = event.data.get(CONF_DEVICE_ID, None)
        session_id = event.data.get(CONF_SESSION_ID, None)
        format = event.data.get(CONF_FORMAT, "GO2RTC")
        if device_id is None or session_id is None:
            return None
        if multi_manager := self._get_correct_multi_manager(source, device_id):
            if account := multi_manager.get_account_by_name(source):
                if (
                    ice_servers
                    := await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                        account.get_webrtc_ice_servers,
                        device_id,
                        session_id,
                        format,
                        self.hass,
                    )
                ):
                    return ice_servers
        return None

    async def _handle_webrtc_debug(
        self, event: XTEventData
    ) -> web.Response | str | None:
        source = event.data.get(CONF_SOURCE, MESSAGE_SOURCE_TUYA_IOT)
        session_id = event.data.get(CONF_SESSION_ID, None)
        if session_id is None:
            return None
        multi_manager_list = get_all_multi_managers(self.hass)
        for multi_manager in multi_manager_list:
            if account := multi_manager.get_account_by_name(source):
                if (
                    debug_output
                    := await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                        account.get_webrtc_exchange_debug, session_id
                    )
                ):
                    return debug_output
        return None

    async def _handle_webrtc_sdp_exchange(
        self, event: XTEventData
    ) -> web.Response | str | None:
        source = event.data.get(CONF_SOURCE, MESSAGE_SOURCE_TUYA_IOT)
        device_id = event.data.get(CONF_DEVICE_ID, None)
        session_id = event.data.get(CONF_SESSION_ID, None)
        channel = event.data.get(CONF_CHANNEL, None)
        if device_id is None or session_id is None:
            return None
        multi_manager = self._get_correct_multi_manager(source, device_id)
        if multi_manager is None or device_id is None or session_id is None:
            return None
        match event.method:
            case "POST":
                match event.content_type:
                    case "application/sdp":
                        if channel is not None:
                            if account := multi_manager.get_account_by_name(source):
                                sdp_answer = await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                                    account.get_webrtc_sdp_answer,
                                    device_id,
                                    session_id,
                                    event.payload,
                                    channel,
                                )
                                if sdp_answer is not None:
                                    response = web.Response(
                                        status=201,
                                        text=sdp_answer,
                                        content_type="application/sdp",
                                        charset="utf-8",
                                    )
                                    response.headers["ETag"] = session_id
                                    response.headers["Location"] = event.location
                                    response.headers["Accept-Patch"] = (
                                        "application/trickle-ice-sdpfrag"
                                    )
                                    return response
                        return None
            case "PATCH":
                match event.content_type:
                    case "application/trickle-ice-sdpfrag":
                        if account := multi_manager.get_account_by_name(source):
                            patch_answer = await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                                account.send_webrtc_trickle_ice,
                                device_id,
                                session_id,
                                event.payload,
                            )
                            if patch_answer is not None:
                                response = web.Response(
                                    status=200, text=patch_answer, charset="utf-8"
                                )
                                response.headers["ETag"] = session_id
                                return response
                        return None
            case "DELETE":
                if account := multi_manager.get_account_by_name(source):
                    delete_answer = (
                        await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                            account.delete_webrtc_session, device_id, session_id
                        )
                    )
                    if delete_answer is not None:
                        response = web.Response(
                            status=200, text=delete_answer, charset="utf-8"
                        )
                        return response
                return None

    async def _handle_fdm5kw_set_timer(
        self, event: XTEventData
    ) -> dict[str, Any] | None:
        from ....entity_parser.fdm5kw.timer_service import set_timer

        ok = await set_timer(self.hass, event.data)
        return {"success": ok}

    async def _handle_fdm5kw_delete_timer(
        self, event: XTEventData
    ) -> dict[str, Any] | None:
        from ....entity_parser.fdm5kw.timer_service import delete_timer

        ok = await delete_timer(self.hass, event.data)
        return {"success": ok}

    async def _handle_fdm5kw_start_watering(
        self, event: XTEventData
    ) -> dict[str, Any] | None:
        from ....entity_parser.fdm5kw.control_service import start_watering

        ok = await start_watering(self.hass, event.data)
        return {"success": ok}

    async def _handle_fdm5kw_stop_watering(
        self, event: XTEventData
    ) -> dict[str, Any] | None:
        from ....entity_parser.fdm5kw.control_service import stop_watering

        ok = await stop_watering(self.hass, event.data)
        return {"success": ok}

    async def _handle_fdm5kw_clear_quota_lockout(
        self, event: XTEventData
    ) -> dict[str, Any] | None:
        from ....entity_parser.fdm5kw.timer_service import clear_quota_lockout

        clear_quota_lockout()
        return {"success": True}

    async def _handle_fdm5kw_resync_timers(
        self, event: XTEventData
    ) -> dict[str, Any] | None:
        from ....entity_parser.fdm5kw.timer_service import resync_from_cloud

        return await resync_from_cloud(self.hass, event.data)
