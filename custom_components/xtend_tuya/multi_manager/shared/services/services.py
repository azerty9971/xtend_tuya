from __future__ import annotations
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from aiohttp import web
from typing import Any
import re
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
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers import device_registry as dr
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.core import SupportsResponse
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

SERVICE_CREATE_TEMP_PASSWORD = "create_temporary_password"
SERVICE_CREATE_TEMP_PASSWORD_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DEVICE_ID): vol.Any(cv.string, [cv.string]),
        vol.Required("password"): cv.string,
        vol.Optional("name"): cv.string,
        vol.Optional("effective_time"): vol.Any(cv.positive_int, cv.string, cv.positive_float),
        vol.Optional("invalid_time"): vol.Any(cv.positive_int, cv.string, cv.positive_float),
        vol.Optional(CONF_SOURCE): cv.string,
    }
)

SERVICE_GET_DYNAMIC_PASSCODE = "get_dynamic_passcode"
SERVICE_GET_DYNAMIC_PASSCODE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DEVICE_ID): vol.Any(cv.string, [cv.string]),
        vol.Optional(CONF_SOURCE): cv.string,
    }
)

SERVICE_GET_TEMP_PASSWORDS = "get_temporary_passwords"
SERVICE_GET_TEMP_PASSWORDS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DEVICE_ID): vol.Any(cv.string, [cv.string]),
        vol.Optional(CONF_SOURCE): cv.string,
    }
)

SERVICE_DELETE_TEMP_PASSWORD = "delete_temporary_password"
SERVICE_DELETE_TEMP_PASSWORD_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DEVICE_ID): vol.Any(cv.string, [cv.string]),
        vol.Required("password_id"): vol.Any(cv.positive_int, cv.string),
        vol.Optional(CONF_SOURCE): cv.string,
    }
)



def parse_time_to_millis(val: Any) -> int | None:
    """Parse integer, float, string datetime or timestamp into milliseconds epoch integer."""
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        if val < 100000000000:
            return int(val * 1000)
        return int(val)
    if isinstance(val, str):
        val_str = val.strip()
        try:
            num = float(val_str)
            if num < 100000000000:
                return int(num * 1000)
            return int(num)
        except ValueError:
            pass

        try:
            from homeassistant.util import dt as dt_util
            if parsed_dt := dt_util.parse_datetime(val_str):
                return int(parsed_dt.timestamp() * 1000)
        except Exception:
            pass

        try:
            from datetime import datetime
            parsed_dt = datetime.fromisoformat(val_str)
            return int(parsed_dt.timestamp() * 1000)
        except Exception as e:
            LOGGER.warning(f"[Tuya Temp Password] Could not parse date string '{val_str}': {e}")
            return None
    return None


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
            SERVICE_CREATE_TEMP_PASSWORD,
            self._handle_create_temp_password,
            SERVICE_CREATE_TEMP_PASSWORD_SCHEMA,
            True,
            True,
            False,
        )
        self._register_service(
            DOMAIN,
            SERVICE_GET_DYNAMIC_PASSCODE,
            self._handle_get_dynamic_passcode,
            SERVICE_GET_DYNAMIC_PASSCODE_SCHEMA,
            True,
            True,
            False,
            supports_response=SupportsResponse.OPTIONAL,
        )
        self._register_service(
            DOMAIN,
            SERVICE_GET_TEMP_PASSWORDS,
            self._handle_get_temp_passwords,
            SERVICE_GET_TEMP_PASSWORDS_SCHEMA,
            True,
            True,
            False,
            supports_response=SupportsResponse.OPTIONAL,
        )
        self._register_service(
            DOMAIN,
            SERVICE_DELETE_TEMP_PASSWORD,
            self._handle_delete_temp_password,
            SERVICE_DELETE_TEMP_PASSWORD_SCHEMA,
            True,
            True,
            False,
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
        supports_response: SupportsResponse | None = None,
    ):
        kwargs = {"schema": schema}
        if supports_response is not None:
            kwargs["supports_response"] = supports_response
        self.hass.services.async_register(domain, name, callback, **kwargs)
        if allow_from_api:
            self.hass.http.register_view(
                XTGeneralView(name, callback, requires_auth, use_cache)
            )

    def _get_correct_multi_manager(
        self, device_id: str
    ) -> mm.MultiManager | None:
        multi_manager, _ = self._resolve_device(device_id)
        return multi_manager

    def _resolve_device(
        self, device_id: str
    ) -> tuple[mm.MultiManager | None, Any | None]:
        multi_manager_list = get_all_multi_managers(self.hass)

        # 1. Direct lookup in multi_manager device_map
        for multi_manager in multi_manager_list:
            if device := multi_manager.device_map.get(device_id):
                return multi_manager, device

        # 2. HA Device Registry lookup for HA registry ID -> Tuya device ID
        try:
            device_registry = dr.async_get(self.hass)
            if ha_device_entry := device_registry.async_get(device_id):
                for _domain, identifier in ha_device_entry.identifiers:
                    for multi_manager in multi_manager_list:
                        if device := multi_manager.device_map.get(identifier):
                            return multi_manager, device
        except Exception as e:
            LOGGER.warning(f"[Tuya Services] Device registry lookup failed for '{device_id}': {e}")

        return None, None

    def _get_account_for_device(
        self, multi_manager: mm.MultiManager, source: str | None
    ) -> Any | None:
        if source and (account := multi_manager.get_account_by_name(source)):
            return account
        if account := multi_manager.get_account_by_name(MESSAGE_SOURCE_TUYA_IOT):
            return account
        if hasattr(multi_manager, "accounts") and multi_manager.accounts:
            return list(multi_manager.accounts.values())[0]
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

    async def _handle_create_temp_password(
        self, event: XTEventData
    ) -> web.Response | dict[str, Any] | None:
        try:
            source = event.data.get(CONF_SOURCE, MESSAGE_SOURCE_TUYA_IOT)
            device_id_raw = event.data.get(CONF_DEVICE_ID, None)
            password = event.data.get("password", None)
            name = event.data.get("name", "HA Temp Password")
            effective_time_raw = event.data.get("effective_time", None)
            invalid_time_raw = event.data.get("invalid_time", None)
            effective_time = parse_time_to_millis(effective_time_raw)
            invalid_time = parse_time_to_millis(invalid_time_raw)

            LOGGER.info(
                f"[Tuya Temp Password Service] Service called for device_id_raw={device_id_raw}, name='{name}', "
                f"eff_time_raw={effective_time_raw} -> {effective_time}, inv_time_raw={invalid_time_raw} -> {invalid_time}"
            )
            if not device_id_raw or not password:
                raise ServiceValidationError(
                    "Missing required parameters: device and password are required.",
                    translation_domain=DOMAIN,
                    translation_key="missing_device_and_password",
                )

            password_str = str(password).strip()
            if not re.match(r"^\d{6,8}$", password_str):
                raise ServiceValidationError(
                    "The PIN must be purely numeric and contain between 6 and 8 digits.",
                    translation_domain=DOMAIN,
                    translation_key="invalid_pin",
                )

            device_ids = device_id_raw if isinstance(device_id_raw, list) else [device_id_raw]
            last_response = None

            for dev_id in device_ids:
                multi_manager, device = self._resolve_device(dev_id)
                if not multi_manager or not device:
                    raise HomeAssistantError(
                        f"Device '{dev_id}' not found in Xtend Tuya integration.",
                        translation_domain=DOMAIN,
                        translation_key="device_not_found",
                        translation_placeholders={"device_id": str(dev_id)},
                    )

                dev_display_name = getattr(device, "name", None) or dev_id
                dev_label = f"'{dev_display_name}' ({dev_id})" if dev_display_name != dev_id else f"'{dev_id}'"

                account = self._get_account_for_device(multi_manager, source)
                if not account:
                    raise HomeAssistantError(
                        f"No valid Tuya account found for device {dev_label}.",
                        translation_domain=DOMAIN,
                        translation_key="no_tuya_account",
                        translation_placeholders={"device": dev_label},
                    )

                target = account
                if not hasattr(target, "create_temporary_password") and hasattr(account, "iot_account") and account.iot_account:
                    target = getattr(account.iot_account, "device_manager", account)

                if not hasattr(target, "create_temporary_password"):
                    raise HomeAssistantError(f"Account target '{target}' does not support create_temporary_password.")

                response = await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                    target.create_temporary_password,
                    device,
                    password_str,
                    name,
                    effective_time,
                    invalid_time,
                )

                if isinstance(response, dict):
                    if not response.get("success", False):
                        msg = response.get("msg") or response.get("error") or "Unknown error from Tuya Cloud"
                        code = response.get("code")
                        if code == 28840002 or "No permissions" in str(msg):
                            err_msg = (
                                f"Tuya API Error for device {dev_label}: No permissions (code {code}). "
                                "Missing 'Smart Lock Service' authorization in iot.tuya.com (Cloud > Development > Your Project > Service API)."
                            )
                            LOGGER.error(f"[Tuya Temp Password Service] {err_msg}")
                            raise HomeAssistantError(
                                err_msg,
                                translation_domain=DOMAIN,
                                translation_key="smart_lock_service_unauthorized",
                                translation_placeholders={"device": dev_label, "code": str(code)},
                            )
                        elif code == 2314 or "password length" in str(msg).lower():
                            err_msg = (
                                f"Tuya API Error for device {dev_label}: Incorrect passcode length (code {code}). "
                                f"This lock requires a numeric PIN of exactly 7 digits (you entered {len(password_str)} digits)."
                            )
                            LOGGER.error(f"[Tuya Temp Password Service] {err_msg}")
                            raise HomeAssistantError(
                                err_msg,
                                translation_domain=DOMAIN,
                                translation_key="lock_requires_7_digits",
                                translation_placeholders={"device": dev_label, "code": str(code), "length": str(len(password_str))},
                            )
                        elif code == 1109:
                            err_msg = (
                                f"Tuya API Error for device {dev_label}: Invalid parameters (code 1109). "
                                "Verify that the PIN and dates are valid for this lock."
                            )
                            LOGGER.error(f"[Tuya Temp Password Service] {err_msg}")
                            raise HomeAssistantError(
                                err_msg,
                                translation_domain=DOMAIN,
                                translation_key="invalid_lock_parameters",
                                translation_placeholders={"device": dev_label, "code": str(code)},
                            )
                        else:
                            err_msg = f"Tuya API Error for device {dev_label}: {msg} (code {code})" if code else f"Tuya API Error for device {dev_label}: {msg}"
                            LOGGER.error(f"[Tuya Temp Password Service] {err_msg}")
                            raise HomeAssistantError(
                                err_msg,
                                translation_domain=DOMAIN,
                                translation_key="tuya_api_error",
                                translation_placeholders={"device": dev_label, "msg": str(msg), "code": str(code) if code else ""},
                            )

                last_response = response

            return last_response
        except (HomeAssistantError, ServiceValidationError):
            raise
        except Exception as e:
            LOGGER.error(f"[Tuya Temp Password Service] Exception in _handle_create_temp_password: {e}", exc_info=True)
            raise HomeAssistantError(
                f"Error creating temporary password: {e}",
                translation_domain=DOMAIN,
                translation_key="action_error",
                translation_placeholders={"action": "create_temporary_password", "error": str(e)},
            ) from e

    async def _handle_webrtc_sdp_exchange(
        self, event: XTEventData
    ) -> web.Response | str | None:
        source = event.data.get(CONF_SOURCE, MESSAGE_SOURCE_TUYA_IOT)
        device_id = event.data.get(CONF_DEVICE_ID, None)
        session_id = event.data.get(CONF_SESSION_ID, None)
        channel = event.data.get(CONF_CHANNEL, None)
        if device_id is None or session_id is None:
            return None
        multi_manager, _device = self._resolve_device(device_id)
        if multi_manager is None or device_id is None or session_id is None:
            return None
        match event.method:
            case "POST":
                match event.content_type:
                    case "application/sdp":
                        if channel is not None:
                            if account := self._get_account_for_device(multi_manager, source):
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
                        if account := self._get_account_for_device(multi_manager, source):
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
                if account := self._get_account_for_device(multi_manager, source):
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

    async def _handle_get_dynamic_passcode(
        self, event: XTEventData
    ) -> dict[str, Any] | None:
        try:
            source = event.data.get(CONF_SOURCE, MESSAGE_SOURCE_TUYA_IOT)
            device_id_raw = event.data.get(CONF_DEVICE_ID, None)
            if not device_id_raw:
                raise ServiceValidationError(
                    "Missing required parameter: device.",
                    translation_domain=DOMAIN,
                    translation_key="missing_device_param",
                )

            device_ids = device_id_raw if isinstance(device_id_raw, list) else [device_id_raw]
            last_response = None

            for dev_id in device_ids:
                multi_manager, device = self._resolve_device(dev_id)
                if not multi_manager or not device:
                    raise HomeAssistantError(
                        f"Device '{dev_id}' not found in Xtend Tuya integration.",
                        translation_domain=DOMAIN,
                        translation_key="device_not_found",
                        translation_placeholders={"device_id": str(dev_id)},
                    )

                dev_display_name = getattr(device, "name", None) or dev_id
                dev_label = f"'{dev_display_name}' ({dev_id})" if dev_display_name != dev_id else f"'{dev_id}'"

                account = self._get_account_for_device(multi_manager, source)
                if not account:
                    raise HomeAssistantError(
                        f"No valid Tuya account found for device {dev_label}.",
                        translation_domain=DOMAIN,
                        translation_key="no_tuya_account",
                        translation_placeholders={"device": dev_label},
                    )

                target = account
                if not hasattr(target, "get_dynamic_password") and hasattr(account, "iot_account") and account.iot_account:
                    target = getattr(account.iot_account, "device_manager", account)

                if not hasattr(target, "get_dynamic_password"):
                    raise HomeAssistantError(f"Account target '{target}' does not support get_dynamic_password.")

                response = await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                    target.get_dynamic_password,
                    device,
                )
                async_dispatcher_send(self.hass, f"xtend_tuya_update_passcode_{device.id}")
                last_response = response

            return last_response
        except (HomeAssistantError, ServiceValidationError):
            raise
        except Exception as e:
            LOGGER.error(f"[Tuya Dynamic Passcode Service] Exception in _handle_get_dynamic_passcode: {e}", exc_info=True)
            raise HomeAssistantError(
                f"Error fetching dynamic passcode: {e}",
                translation_domain=DOMAIN,
                translation_key="action_error",
                translation_placeholders={"action": "get_dynamic_passcode", "error": str(e)},
            ) from e

    async def _handle_get_temp_passwords(
        self, event: XTEventData
    ) -> dict[str, Any] | None:
        try:
            source = event.data.get(CONF_SOURCE, MESSAGE_SOURCE_TUYA_IOT)
            device_id_raw = event.data.get(CONF_DEVICE_ID, None)
            if not device_id_raw:
                raise ServiceValidationError(
                    "Missing required parameter: device.",
                    translation_domain=DOMAIN,
                    translation_key="missing_device_param",
                )

            device_ids = device_id_raw if isinstance(device_id_raw, list) else [device_id_raw]
            all_passwords = []

            for dev_id in device_ids:
                multi_manager, device = self._resolve_device(dev_id)
                if not multi_manager or not device:
                    raise HomeAssistantError(
                        f"Device '{dev_id}' not found in Xtend Tuya integration.",
                        translation_domain=DOMAIN,
                        translation_key="device_not_found",
                        translation_placeholders={"device_id": str(dev_id)},
                    )

                dev_display_name = getattr(device, "name", None) or dev_id
                dev_label = f"'{dev_display_name}' ({dev_id})" if dev_display_name != dev_id else f"'{dev_id}'"

                account = self._get_account_for_device(multi_manager, source)
                if not account:
                    raise HomeAssistantError(
                        f"No valid Tuya account found for device {dev_label}.",
                        translation_domain=DOMAIN,
                        translation_key="no_tuya_account",
                        translation_placeholders={"device": dev_label},
                    )

                target = account
                if not hasattr(target, "get_temporary_passwords") and hasattr(account, "iot_account") and account.iot_account:
                    target = getattr(account.iot_account, "device_manager", account)

                if not hasattr(target, "get_temporary_passwords"):
                    raise HomeAssistantError(f"Account target '{target}' does not support get_temporary_passwords.")

                response = await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                    target.get_temporary_passwords,
                    device,
                )
                if isinstance(response, list):
                    for p in response:
                        if isinstance(p, dict):
                            p_copy = dict(p)
                            p_copy["device_id"] = device.id
                            p_copy["device_name"] = getattr(device, "name", dev_id)
                            all_passwords.append(p_copy)
                        else:
                            all_passwords.append(p)

            return {"passwords": all_passwords}
        except (HomeAssistantError, ServiceValidationError):
            raise
        except Exception as e:
            LOGGER.error(f"[Tuya Temp Password Service] Exception in _handle_get_temp_passwords: {e}", exc_info=True)
            raise HomeAssistantError(
                f"Error fetching temporary passwords: {e}",
                translation_domain=DOMAIN,
                translation_key="action_error",
                translation_placeholders={"action": "get_temporary_passwords", "error": str(e)},
            ) from e

    async def _handle_delete_temp_password(
        self, event: XTEventData
    ) -> dict[str, Any] | None:
        try:
            source = event.data.get(CONF_SOURCE, MESSAGE_SOURCE_TUYA_IOT)
            device_id_raw = event.data.get(CONF_DEVICE_ID, None)
            password_id = event.data.get("password_id", None)
            if not device_id_raw or password_id is None:
                raise ServiceValidationError(
                    "Missing required parameters: device and password_id are required.",
                    translation_domain=DOMAIN,
                    translation_key="missing_device_and_password_id",
                )

            device_ids = device_id_raw if isinstance(device_id_raw, list) else [device_id_raw]
            any_success = False
            last_error_args = None

            for dev_id in device_ids:
                multi_manager, device = self._resolve_device(dev_id)
                if not multi_manager or not device:
                    raise HomeAssistantError(
                        f"Device '{dev_id}' not found in Xtend Tuya integration.",
                        translation_domain=DOMAIN,
                        translation_key="device_not_found",
                        translation_placeholders={"device_id": str(dev_id)},
                    )

                dev_display_name = getattr(device, "name", None) or dev_id
                dev_label = f"'{dev_display_name}' ({dev_id})" if dev_display_name != dev_id else f"'{dev_id}'"

                account = self._get_account_for_device(multi_manager, source)
                if not account:
                    raise HomeAssistantError(
                        f"No valid Tuya account found for device {dev_label}.",
                        translation_domain=DOMAIN,
                        translation_key="no_tuya_account",
                        translation_placeholders={"device": dev_label},
                    )

                target = account
                if not hasattr(target, "delete_temporary_password") and hasattr(account, "iot_account") and account.iot_account:
                    target = getattr(account.iot_account, "device_manager", account)

                if not hasattr(target, "delete_temporary_password"):
                    raise HomeAssistantError(f"Account target '{target}' does not support delete_temporary_password.")

                response = await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                    target.delete_temporary_password,
                    device,
                    password_id,
                )

                if isinstance(response, dict):
                    if response.get("success", False):
                        any_success = True
                        last_response = response
                    else:
                        msg = response.get("msg") or response.get("error") or "Unknown error from Tuya Cloud"
                        code = response.get("code")
                        err_msg = f"Tuya API Error for device {dev_label}: {msg} (code {code})" if code else f"Tuya API Error for device {dev_label}: {msg}"
                        LOGGER.warning(f"[Tuya Temp Password Service] {err_msg}")
                        last_error_args = {
                            "err_msg": err_msg,
                            "placeholders": {"device": dev_label, "msg": str(msg), "code": str(code) if code else ""},
                        }
                else:
                    last_response = response

            if not any_success and last_error_args:
                raise HomeAssistantError(
                    last_error_args["err_msg"],
                    translation_domain=DOMAIN,
                    translation_key="tuya_api_error",
                    translation_placeholders=last_error_args["placeholders"],
                )

            return last_response or {"success": True}
        except (HomeAssistantError, ServiceValidationError):
            raise
        except Exception as e:
            LOGGER.error(f"[Tuya Temp Password Service] Exception in _handle_delete_temp_password: {e}", exc_info=True)
            raise HomeAssistantError(
                f"Error deleting temporary password: {e}",
                translation_domain=DOMAIN,
                translation_key="action_error",
                translation_placeholders={"action": "delete_temporary_password", "error": str(e)},
            ) from e


