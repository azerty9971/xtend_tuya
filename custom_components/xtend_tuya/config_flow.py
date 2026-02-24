"""Config flow for Tuya."""

from __future__ import annotations
from collections.abc import Mapping
from typing import Any, cast
from enum import StrEnum
from tuya_sharing import LoginControl
from .lib.tuya_iot import AuthType
import voluptuous as vol
import functools
from homeassistant.core import callback, HomeAssistant
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
    ConfigEntryBaseFlow,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.typing import (
    DiscoveryInfoType,
)
from .const import (
    TuyaCloudOpenAPIEndpoint,
    CONF_ENDPOINT,
    CONF_TERMINAL_ID,
    CONF_TOKEN_INFO,
    CONF_USER_CODE,
    DOMAIN,
    TUYA_CLIENT_ID,
    TUYA_RESPONSE_CODE,
    TUYA_RESPONSE_MSG,
    TUYA_RESPONSE_QR_CODE,
    TUYA_RESPONSE_RESULT,
    TUYA_RESPONSE_SUCCESS,
    TUYA_SCHEMA,
    CONF_ACCESS_ID_OT,
    CONF_ACCESS_SECRET_OT,
    CONF_APP_TYPE,
    CONF_ENDPOINT_OT,
    CONF_AUTH_TYPE,
    CONF_COUNTRY_CODE,
    CONF_NO_OPENAPI,
    CONF_PASSWORD_OT,
    CONF_USERNAME,
    CONF_USERNAME_OT,
    SMARTLIFE_APP,
    TUYA_COUNTRIES,
    TUYA_SMART_APP,
    TUYA_RESPONSE_PLATFORM_URL,
    XTDiscoverySource,
)
from .multi_manager.shared.threading import (
    XTEventLoopProtector,
    XTConcurrencyManager,
)
from .multi_manager.managers.tuya_iot.xt_tuya_iot_openapi import XTIOTOpenAPI
import custom_components.xtend_tuya.util as util
import custom_components.xtend_tuya.multi_manager.multi_manager as mm
import custom_components.xtend_tuya.multi_manager.shared.data_entry.shared_data_entry as data_entry

STEP_METHOD_PREFIX = "async_step_"


class XTStepId(StrEnum):
    CONFIGURE = "configure"
    CONFIGURE_API = "configure_api"
    DEVICE_SETTINGS = "device_settings"
    SELECT_CLIMATE_DEVICE = "select_climate_device"
    CLIMATE_DEVICE_SETTINGS = "climate_device_settings"


OPTION_STEP_DEFINITION: dict[XTStepId, tuple[str, list[Any], dict[str, Any]]] = {
    XTStepId.CONFIGURE: (
        "async_show_menu",
        [],
        {
            "step_id": XTStepId.CONFIGURE,
            "menu_options": [XTStepId.CONFIGURE_API, XTStepId.DEVICE_SETTINGS],
        },
    ),
    XTStepId.DEVICE_SETTINGS: (
        "async_show_menu",
        [],
        {
            "step_id": XTStepId.DEVICE_SETTINGS,
            "menu_options": [XTStepId.SELECT_CLIMATE_DEVICE],
        },
    ),
    XTStepId.SELECT_CLIMATE_DEVICE: (
        "async_step_select_device",
        [],
        {
            "user_input": None,
            "has_preferences": {f"{mm.XTDevice.XTDevicePreference.IS_A_CLIMATE_DEVICE}": True},
            "next_step_id": XTStepId.CLIMATE_DEVICE_SETTINGS,
        },
    ),
}


class XTConfigFlows:
    class XTStepResultType(StrEnum):
        RESULT = "RESULT"
        SHOW_FORM = "SHOW_FORM"

    def __init__(
        self, parent: ConfigEntryBaseFlow, config_entry: ConfigEntry | None = None
    ) -> None:
        self.config_entry = config_entry
        if self.config_entry is not None:
            self.options = self.config_entry.options
        else:
            self.options = {}
        self.parent = parent

    def async_create_entry(self, *args, **kwargs):
        return self.parent.async_create_entry(*args, **kwargs)

    def async_show_form(self, *args, **kwargs):
        return self.parent.async_show_form(*args, **kwargs)

    @staticmethod
    def _try_login_open_api(
        user_input: dict[str, Any], hass: HomeAssistant
    ) -> tuple[dict[Any, Any], dict[str, Any]]:
        """Try login."""
        response = {}

        country = [
            country
            for country in TUYA_COUNTRIES
            if country.name == user_input[CONF_COUNTRY_CODE]
        ][0]

        data = {
            CONF_NO_OPENAPI: user_input[CONF_NO_OPENAPI],
            CONF_ENDPOINT_OT: user_input[CONF_ENDPOINT_OT],
            CONF_AUTH_TYPE: AuthType.CUSTOM,
            CONF_ACCESS_ID_OT: user_input[CONF_ACCESS_ID_OT],
            CONF_ACCESS_SECRET_OT: user_input[CONF_ACCESS_SECRET_OT],
            CONF_USERNAME_OT: user_input[CONF_USERNAME_OT],
            CONF_PASSWORD_OT: user_input[CONF_PASSWORD_OT],
            CONF_COUNTRY_CODE: country.country_code,
        }
        if data[CONF_NO_OPENAPI] is True:
            data[CONF_ACCESS_ID_OT] = None
            data[CONF_ACCESS_SECRET_OT] = None
            data[CONF_USERNAME_OT] = None
            data[CONF_PASSWORD_OT] = None
            return {TUYA_RESPONSE_SUCCESS: True}, data

        for app_type in ("", TUYA_SMART_APP, SMARTLIFE_APP):
            data[CONF_APP_TYPE] = app_type
            if data[CONF_APP_TYPE] == "":
                data[CONF_AUTH_TYPE] = AuthType.CUSTOM
            else:
                data[CONF_AUTH_TYPE] = AuthType.SMART_HOME

            api = XTIOTOpenAPI(
                endpoint=data[CONF_ENDPOINT_OT],
                access_id=data[CONF_ACCESS_ID_OT],
                access_secret=data[CONF_ACCESS_SECRET_OT],
                auth_type=data[CONF_AUTH_TYPE],
            )
            api.set_dev_channel("hass")

            response = api.connect(
                username=data[CONF_USERNAME_OT],
                password=data[CONF_PASSWORD_OT],
                country_code=data[CONF_COUNTRY_CODE],
                schema=data[CONF_APP_TYPE],
            )

            if response.get(TUYA_RESPONSE_SUCCESS, False):
                break

        return response, data

    async def async_step_configure(
        self, user_input: dict[str, Any] | None = None
    ) -> tuple[XTConfigFlows.XTStepResultType, ConfigFlowResult | dict[str, str]]:
        """Manage the options."""
        errors = {}
        placeholders = {}

        if user_input is not None:
            (
                response,
                data,
            ) = await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                self._try_login_open_api, user_input, self.parent.hass
            )

            if response.get(TUYA_RESPONSE_SUCCESS, False):
                if endpoint := response.get(TUYA_RESPONSE_RESULT, {}).get(
                    TUYA_RESPONSE_PLATFORM_URL
                ):
                    data[CONF_ENDPOINT_OT] = endpoint

                data[CONF_AUTH_TYPE] = data[CONF_AUTH_TYPE].value

                return (XTConfigFlows.XTStepResultType.RESULT, data)
            errors["base"] = "login_error"
            placeholders = {
                TUYA_RESPONSE_CODE: response.get(TUYA_RESPONSE_CODE, "0"),
                TUYA_RESPONSE_MSG: response.get(TUYA_RESPONSE_MSG, "Unknown error"),
            }

        if user_input is None:
            user_input = {}

        default_country = "United States"
        default_endpoint = TuyaCloudOpenAPIEndpoint.AMERICA
        if self.options is not None:
            country_code = self.options.get(CONF_COUNTRY_CODE, "")
            if country_code != "":
                for country in TUYA_COUNTRIES:
                    if country.country_code == country_code:
                        default_country = country.name
                        break
            default_endpoint = self.options.get(CONF_ENDPOINT_OT, "")
            if default_endpoint == "" and country_code != "":
                for country in TUYA_COUNTRIES:
                    if country.country_code == country_code:
                        default_endpoint = country.endpoint
                        break

        return (
            XTConfigFlows.XTStepResultType.SHOW_FORM,
            self.async_show_form(
                step_id="configure",
                data_schema=vol.Schema(
                    {
                        vol.Optional(
                            CONF_NO_OPENAPI,
                            default=bool(
                                user_input.get(
                                    CONF_NO_OPENAPI,
                                    self.options.get(CONF_NO_OPENAPI, ""),
                                )
                            ),
                        ): bool,
                        vol.Optional(
                            CONF_COUNTRY_CODE,
                            default=user_input.get(CONF_COUNTRY_CODE, default_country),
                        ): vol.In(
                            # We don't pass a dict {code:name} because country codes can be duplicate.
                            [country.name for country in TUYA_COUNTRIES]
                        ),
                        vol.Optional(
                            CONF_ENDPOINT_OT,
                            default=user_input.get(CONF_ENDPOINT_OT, default_endpoint),
                        ): vol.In(
                            {
                                endpoint.value: endpoint.get_human_name(endpoint.value)
                                for endpoint in TuyaCloudOpenAPIEndpoint
                            }
                        ),
                        vol.Optional(
                            CONF_ACCESS_ID_OT,
                            default=user_input.get(
                                CONF_ACCESS_ID_OT,
                                self.options.get(CONF_ACCESS_ID_OT, ""),
                            ),
                        ): str,
                        vol.Optional(
                            CONF_ACCESS_SECRET_OT,
                            default=user_input.get(
                                CONF_ACCESS_SECRET_OT,
                                self.options.get(CONF_ACCESS_SECRET_OT, ""),
                            ),
                        ): str,
                        vol.Optional(
                            CONF_USERNAME_OT,
                            default=user_input.get(
                                CONF_USERNAME_OT, self.options.get(CONF_USERNAME_OT, "")
                            ),
                        ): str,
                        vol.Optional(
                            CONF_PASSWORD_OT,
                            default=user_input.get(
                                CONF_PASSWORD_OT, self.options.get(CONF_PASSWORD_OT, "")
                            ),
                        ): str,
                    }
                ),
                errors=errors,
                description_placeholders=placeholders,
            ),
        )


class TuyaOptionFlow(OptionsFlow):
    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.handler = config_entry.entry_id
        self.xt_config_entry = config_entry
        self.selected_device_id: str | None = None
        self.selected_device_next_step_id: str | None = None
        self._device_options: dict[str, str] = {}
        self.multi_manager: mm.MultiManager | None = getattr(config_entry.runtime_data, "multi_manager") if config_entry.runtime_data else None
        if config_entry.options is not None:
            self.options = config_entry.options
        else:
            self.options = {}

    def __getattr__(self, name: str):
        step_prefix: str = STEP_METHOD_PREFIX
        step_postfix = name[len(step_prefix) :]
        if name.startswith(step_prefix) and step_postfix in OPTION_STEP_DEFINITION:
            if function := getattr(
                self, OPTION_STEP_DEFINITION[XTStepId(step_postfix)][0]
            ):

                async def wrapper(
                    user_input: dict[str, Any] | None = None,
                ) -> ConfigFlowResult:
                    return function(
                        *OPTION_STEP_DEFINITION[XTStepId(step_postfix)][1],
                        **OPTION_STEP_DEFINITION[XTStepId(step_postfix)][2],
                    )

                return wrapper

        raise AttributeError

    async def async_step_configure_api(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        result_type, data = await XTConfigFlows(
            self, self.xt_config_entry
        ).async_step_configure(user_input=user_input)
        match result_type:
            case XTConfigFlows.XTStepResultType.SHOW_FORM:
                data = cast(ConfigFlowResult, data)
                return data
            case XTConfigFlows.XTStepResultType.RESULT:
                data = cast(dict[str, str], data)
                # Preserve device_settings when updating API config
                if "device_settings" in self.options:
                    data["device_settings"] = self.options["device_settings"]
                return self.async_create_entry(title="", data=data)

    async def async_step_select_device(
        self,
        user_input: dict[str, Any] | None = None,
        has_preferences: dict[str, Any] | None = None,
        next_step_id: str | None = None,
    ) -> ConfigFlowResult:
        """Handle device settings step."""
        if next_step_id is not None:
            self.selected_device_next_step_id = next_step_id
        if user_input is not None:
            self.selected_device_id = user_input.get("device")
            if self.selected_device_id is not None:
                if function := getattr(self, f"{STEP_METHOD_PREFIX}{self.selected_device_next_step_id}", None):
                    return await function()

        # Get devices based on preferences
        self._device_options = {}
        if self.multi_manager is not None:
            for (
                device_id,
                device,
            ) in self.multi_manager.device_map.items():
                if has_preferences is not None:
                    for has_preference in has_preferences:
                        preference_value = device.get_preference(has_preference, None)
                        if preference_value is not None:
                            if preference_value == has_preferences[has_preference]:
                                self._device_options[device_id] = f"{device.name} ({device.id})"

        # Fallback if no devices found or runtime data not available
        if not self._device_options:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="select_device",
            data_schema=vol.Schema(
                {
                    vol.Required("device"): vol.In(self._device_options),
                }
            ),
        )

    async def async_step_climate_device_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device configuration."""
        if user_input is not None:
            # Update options, preserving all existing settings
            new_options = dict(self.options)
            if "device_settings" not in new_options:
                new_options["device_settings"] = {}
            else:
                new_options["device_settings"] = dict(new_options["device_settings"])

            # Preserve other settings for this device
            current_device_settings = dict(
                new_options["device_settings"].get(self.selected_device_id, {})
            )
            current_device_settings["target_temperature_step"] = user_input[
                "target_temperature_step"
            ]
            new_options["device_settings"][
                self.selected_device_id
            ] = current_device_settings

            return self.async_create_entry(title="", data=new_options)

        # Get current setting for this device
        current_step = 0.5
        if (
            "device_settings" in self.options
            and self.selected_device_id in self.options["device_settings"]
        ):
            current_step = self.options["device_settings"][self.selected_device_id].get(
                "target_temperature_step", 0.5
            )

        return self.async_show_form(
            step_id="climate_device_settings",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "target_temperature_step",
                        default=current_step,
                    ): vol.In(
                        {
                            0.1: "0.1 (raw value: 1)",
                            0.5: "0.5 (raw value: 5)",
                            1.0: "1.0 (raw value: 10)",
                        }
                    ),
                }
            ),
            description_placeholders={
                "device_name": self.selected_device_id or "",
            },
        )


class TuyaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Tuya config flow."""

    __user_code: str
    __qr_code: str
    __reauth_entry: ConfigEntry | None = None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.__login_control = LoginControl()
        self.config_entry_data: dict[str, str] = {}
        self.config_entry_title: str = ""

    def __getattr__(self, name: str):
        step_prefix: str = STEP_METHOD_PREFIX
        if (
            name.startswith(step_prefix)
            and name[len(step_prefix) :] in XTDiscoverySource
        ):
            return self.generic_data_entry
        else:
            raise AttributeError

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return TuyaOptionFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step user."""
        errors = {}
        placeholders = {}

        XTEventLoopProtector.hass = self.hass
        XTConcurrencyManager.hass = self.hass

        if user_input is not None:
            success, response = await self.__async_get_qr_code(
                user_input[CONF_USER_CODE]
            )
            if success:
                return await self.async_step_scan()

            errors["base"] = "login_error"
            placeholders = {
                TUYA_RESPONSE_MSG: response.get(TUYA_RESPONSE_MSG, "Unknown error"),
                TUYA_RESPONSE_CODE: response.get(TUYA_RESPONSE_CODE, "0"),
            }
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USER_CODE, default=user_input.get(CONF_USER_CODE, "")
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_configure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        result_type, data = await XTConfigFlows(
            self, config_entry=None
        ).async_step_configure(user_input=user_input)
        match result_type:
            case XTConfigFlows.XTStepResultType.SHOW_FORM:
                data = cast(ConfigFlowResult, data)
                return data
            case XTConfigFlows.XTStepResultType.RESULT:
                data = cast(dict[str, str], data)
                return self.async_create_entry(
                    title=self.config_entry_title,
                    data=self.config_entry_data,
                    options=data,
                )

    async def async_step_scan(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step scan."""
        if user_input is None:
            return self.async_show_form(
                step_id="scan",
                data_schema=vol.Schema(
                    {
                        vol.Optional("QR"): selector.QrCodeSelector(
                            config=selector.QrCodeSelectorConfig(
                                data=f"tuyaSmart--qrLogin?token={self.__qr_code}",
                                scale=5,
                                error_correction_level=selector.QrErrorCorrectionLevel.QUARTILE,
                            )
                        )
                    }
                ),
            )

        ret, info = await XTEventLoopProtector.execute_out_of_event_loop_and_return(
            self.__login_control.login_result,
            self.__qr_code,
            TUYA_CLIENT_ID,
            self.__user_code,
        )
        if not ret:
            # Try to get a new QR code on failure
            await self.__async_get_qr_code(self.__user_code)
            return self.async_show_form(
                step_id="scan",
                errors={"base": "login_error"},
                data_schema=vol.Schema(
                    {
                        vol.Optional("QR"): selector.QrCodeSelector(
                            config=selector.QrCodeSelectorConfig(
                                data=f"tuyaSmart--qrLogin?token={self.__qr_code}",
                                scale=5,
                                error_correction_level=selector.QrErrorCorrectionLevel.QUARTILE,
                            )
                        )
                    }
                ),
                description_placeholders={
                    TUYA_RESPONSE_MSG: info.get(TUYA_RESPONSE_MSG, "Unknown error"),
                    TUYA_RESPONSE_CODE: info.get(TUYA_RESPONSE_CODE, 0),
                },
            )

        entry_data = {
            CONF_USER_CODE: self.__user_code,
            CONF_TOKEN_INFO: {
                "t": info["t"],
                "uid": info["uid"],
                "expire_time": info["expire_time"],
                "access_token": info["access_token"],
                "refresh_token": info["refresh_token"],
            },
            CONF_TERMINAL_ID: info[CONF_TERMINAL_ID],
            CONF_ENDPOINT: info[CONF_ENDPOINT],
            CONF_USERNAME: info.get("username", ""),
        }

        if self.__reauth_entry:
            return self.async_update_reload_and_abort(
                self.__reauth_entry,
                data=entry_data,
            )

        self.config_entry_data = entry_data
        self.config_entry_title = info.get("username", "")
        return await self.async_step_configure()

    async def async_step_reauth(self, _: Mapping[str, Any]) -> ConfigFlowResult:
        """Handle initiation of re-authentication with Tuya."""
        if entry_id := self.context.get("entry_id"):
            self.__reauth_entry = self.hass.config_entries.async_get_entry(entry_id)

        if self.__reauth_entry and CONF_USER_CODE in self.__reauth_entry.data:
            success, _ = await self.__async_get_qr_code(
                self.__reauth_entry.data[CONF_USER_CODE]
            )
            if success:
                return await self.async_step_scan()

        return await self.async_step_reauth_user_code()

    async def async_step_reauth_user_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication with a Tuya."""
        errors = {}
        placeholders = {}

        if user_input is not None:
            success, response = await self.__async_get_qr_code(
                user_input[CONF_USER_CODE]
            )
            if success:
                return await self.async_step_scan()

            errors["base"] = "login_error"
            placeholders = {
                TUYA_RESPONSE_MSG: response.get(TUYA_RESPONSE_MSG, "Unknown error"),
                TUYA_RESPONSE_CODE: response.get(TUYA_RESPONSE_CODE, "0"),
            }
        else:
            user_input = {}

        return self.async_show_form(
            step_id="reauth_user_code",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USER_CODE, default=user_input.get(CONF_USER_CODE, "")
                    ): str,
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def get_overriden_data_entry(self) -> data_entry.XTFlowDataBase | None:
        all_mm: list[mm.MultiManager] = util.get_all_multi_managers(self.hass)
        handler: data_entry.XTFlowDataBase | None = None
        for multimanager in all_mm:
            if handler := multimanager.get_user_input_data(self.flow_id):
                return handler
        return None

    async def generic_data_entry(
        self, discovery_info: DiscoveryInfoType | data_entry.XTFlowDataBase | None
    ) -> ConfigFlowResult:
        if isinstance(discovery_info, data_entry.XTFlowDataBase):
            handler = discovery_info
            if handler.flow_id is None:
                handler.flow_id = self.flow_id
                handler.multi_manager.register_user_input_data(handler)
            return await handler.processing_class.user_interaction_callback(self, None)
        else:
            if handler := await self.get_overriden_data_entry():
                return await handler.processing_class.user_interaction_callback(
                    self, discovery_info
                )
        return self.async_abort(
            reason="Xtend Tuya processing function didn't return a handler, contact the developer"
        )

    async def __async_get_qr_code(self, user_code: str) -> tuple[bool, dict[str, Any]]:
        """Get the QR code."""
        response = await XTEventLoopProtector.execute_out_of_event_loop_and_return(
            self.__login_control.qr_code,
            TUYA_CLIENT_ID,
            TUYA_SCHEMA,
            user_code,
        )
        if success := response.get(TUYA_RESPONSE_SUCCESS, False):
            self.__user_code = user_code
            self.__qr_code = response[TUYA_RESPONSE_RESULT][TUYA_RESPONSE_QR_CODE]
        return success, response
