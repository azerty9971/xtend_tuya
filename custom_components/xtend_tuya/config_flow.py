"""Config flow for Tuya."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tuya_sharing import LoginControl
from tuya_iot import AuthType, TuyaOpenAPI
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
try:
    from homeassistant.config_entries import ConfigFlowResult
except ImportError:
    from homeassistant.data_entry_flow import FlowResult
    type ConfigFlowResult = FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_ENDPOINT,
    CONF_TERMINAL_ID,
    CONF_TOKEN_INFO,
    CONF_USER_CODE,
    DOMAIN,
    DOMAIN_ORIG,
    LOGGER,
    TUYA_CLIENT_ID,
    TUYA_RESPONSE_CODE,
    TUYA_RESPONSE_MSG,
    TUYA_RESPONSE_QR_CODE,
    TUYA_RESPONSE_RESULT,
    TUYA_RESPONSE_SUCCESS,
    TUYA_SCHEMA,
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_APP_TYPE,
    CONF_ENDPOINT_OT,
    CONF_AUTH_TYPE,
    CONF_COUNTRY_CODE,
    CONF_PASSWORD,
    CONF_USERNAME,
    SMARTLIFE_APP,
    TUYA_COUNTRIES,
    TUYA_SMART_APP,
    TUYA_RESPONSE_PLATFORM_URL,
)


class TuyaOptionFlow(OptionsFlow):
    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_COUNTRY_CODE,
                    ): vol.In(
                        # We don't pass a dict {code:name} because country codes can be duplicate.
                        [country.name for country in TUYA_COUNTRIES]
                    ),
                    vol.Optional(
                        CONF_ACCESS_ID, default=user_input.get(CONF_ACCESS_ID, "")
                    ): str,
                    vol.Optional(
                        CONF_ACCESS_SECRET,
                        default=user_input.get(CONF_ACCESS_SECRET, ""),
                    ): str,
                    vol.Optional(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                    ): str,
                    vol.Optional(
                        CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                    ): str,
                }
            ),
        )

class TuyaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Tuya config flow."""

    __user_code: str
    __qr_code: str
    __reauth_entry: ConfigEntry | None = None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.__login_control = LoginControl()
    
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return TuyaOptionFlow(config_entry)
    
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step user."""
        tuya_data = self.hass.config_entries.async_entries(DOMAIN_ORIG,False,False)
        xt_tuya_data = self.hass.config_entries.async_entries(DOMAIN,True,True)
        if tuya_data:
            for config_entry in tuya_data:
                xt_tuya_config_already_exists = False
                for xt_tuya_config in xt_tuya_data:
                    if xt_tuya_config.title == config_entry.title:
                        xt_tuya_config_already_exists = True
                        break
                if not xt_tuya_config_already_exists:
                    return self.async_create_entry(
                        title=config_entry.title,
                        data=config_entry.data,
                    )
        else:
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

        return self.async_abort(reason="No unimported Tuya configuration")

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

        ret, info = await self.hass.async_add_executor_job(
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
        }

        if self.__reauth_entry:
            return self.async_update_reload_and_abort(
                self.__reauth_entry,
                data=entry_data,
            )

        return self.async_create_entry(
            title=info.get("username"),
            data=entry_data,
        )

    async def async_step_reauth(self, _: Mapping[str, Any]) -> ConfigFlowResult:
        """Handle initiation of re-authentication with Tuya."""
        self.__reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )

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

    async def __async_get_qr_code(self, user_code: str) -> tuple[bool, dict[str, Any]]:
        """Get the QR code."""
        response = await self.hass.async_add_executor_job(
            self.__login_control.qr_code,
            TUYA_CLIENT_ID,
            TUYA_SCHEMA,
            user_code,
        )
        if success := response.get(TUYA_RESPONSE_SUCCESS, False):
            self.__user_code = user_code
            self.__qr_code = response[TUYA_RESPONSE_RESULT][TUYA_RESPONSE_QR_CODE]
        return success, response
