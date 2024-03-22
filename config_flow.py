"""Config flow for Tuya."""
from __future__ import annotations

from typing import Any

from tuya_iot import AuthType, TuyaOpenAPI
import voluptuous as vol

from homeassistant import config_entries

from .const import (
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_APP_TYPE,
    CONF_AUTH_TYPE,
    CONF_COUNTRY_CODE,
    CONF_ENDPOINT,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
    DOMAIN_ORIG,
    LOGGER,
    SMARTLIFE_APP,
    TUYA_COUNTRIES,
    TUYA_RESPONSE_CODE,
    TUYA_RESPONSE_MSG,
    TUYA_RESPONSE_PLATFORM_URL,
    TUYA_RESPONSE_RESULT,
    TUYA_RESPONSE_SUCCESS,
    TUYA_SMART_APP,
)


class TuyaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Tuya Config Flow."""

    @staticmethod
    def _try_login(user_input: dict[str, Any]) -> tuple[dict[Any, Any], dict[str, Any]]:
        """Try login."""
        response = {}

        country = [
            country
            for country in TUYA_COUNTRIES
            if country.name == user_input[CONF_COUNTRY_CODE]
        ][0]

        data = {
            CONF_ENDPOINT: country.endpoint,
            CONF_AUTH_TYPE: AuthType.CUSTOM,
            CONF_ACCESS_ID: user_input[CONF_ACCESS_ID],
            CONF_ACCESS_SECRET: user_input[CONF_ACCESS_SECRET],
            CONF_USERNAME: user_input[CONF_USERNAME],
            CONF_PASSWORD: user_input[CONF_PASSWORD],
            CONF_COUNTRY_CODE: country.country_code,
        }

        for app_type in ("", TUYA_SMART_APP, SMARTLIFE_APP):
            data[CONF_APP_TYPE] = app_type
            if data[CONF_APP_TYPE] == "":
                data[CONF_AUTH_TYPE] = AuthType.CUSTOM
            else:
                data[CONF_AUTH_TYPE] = AuthType.SMART_HOME

            api = TuyaOpenAPI(
                endpoint=data[CONF_ENDPOINT],
                access_id=data[CONF_ACCESS_ID],
                access_secret=data[CONF_ACCESS_SECRET],
                auth_type=data[CONF_AUTH_TYPE],
            )
            api.set_dev_channel("hass")

            response = api.connect(
                username=data[CONF_USERNAME],
                password=data[CONF_PASSWORD],
                country_code=data[CONF_COUNTRY_CODE],
                schema=data[CONF_APP_TYPE],
            )

            LOGGER.debug("Response %s", response)

            if response.get(TUYA_RESPONSE_SUCCESS, False):
                break

        return response, data

    async def async_step_user(self, user_input=None):
        """Step user."""
        if DOMAIN_ORIG in self.hass.data:
            tuya_data = self.hass.data[DOMAIN_ORIG]
            for config in tuya_data:
                config_entry = self.hass.config_entries.async_get_entry(config)
                """LOGGER.debug(f"config_entry -> {vars(config_entry)}")"""
                return self.async_create_entry(
                    title=config_entry.title,
                    data=config_entry.data,
                )
        
        return self.async_abort(reason="tuya_not_configured")
