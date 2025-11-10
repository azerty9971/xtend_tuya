"""Tuya Open API."""

from __future__ import annotations
import time
import json  # noqa: F401
import hashlib
import hmac
from typing import Any
from datetime import datetime
from ....lib.tuya_iot import (
    TuyaOpenAPI,
    TuyaTokenInfo,
)
from homeassistant.core import (
    HomeAssistant,
)
from ....lib.tuya_iot.tuya_enums import AuthType
from ....lib.tuya_iot.version import VERSION
from ....const import (
    LOGGER,
)

TUYA_ERROR_CODE_TOKEN_INVALID = 1010

TO_C_CUSTOM_REFRESH_TOKEN_API = "/v1.0/iot-03/users/token/"
TO_C_SMART_HOME_REFRESH_TOKEN_API = "/v1.0/token/"

TO_C_CUSTOM_TOKEN_API = "/v1.0/iot-03/users/login"
TO_C_SMART_HOME_TOKEN_API = "/v1.0/iot-01/associated-users/actions/authorized-login"
TO_C_SMART_HOME_TOKEN_API_NEW = "/v1.0/token"


class XTTokenInfo(TuyaTokenInfo):
    """Tuya token info.

    Attributes:
        access_token: Access token.
        expire_time: Valid period in seconds.
        refresh_token: Refresh token.
        uid: Tuya user ID.
        platform_url: user region platform url
    """

    def __init__(self, token_response: dict[str, Any] = {}):
        """Init TuyaTokenInfo."""
        super().__init__(token_response = token_response)


class XTIOTOpenAPI(TuyaOpenAPI):
    """Open Api.

    Typical usage example:

    openapi = TuyaOpenAPI(ENDPOINT, ACCESS_ID, ACCESS_KEY)
    """

    def __init__(
        self,
        hass: HomeAssistant,
        endpoint: str,
        access_id: str,
        access_secret: str,
        auth_type: AuthType = AuthType.SMART_HOME,
        lang: str = "en",
        non_user_specific_api: bool = False,
    ) -> None:
        """Init TuyaOpenAPI."""
        super(XTIOTOpenAPI, self).__init__(
            endpoint=endpoint,
            access_id=access_id,
            access_secret=access_secret,
            auth_type=auth_type,
            lang=lang,
        )
        self.hass = hass
        self.non_user_specific_api = non_user_specific_api
        if self.auth_type == AuthType.CUSTOM:
            self.__login_path = TO_C_CUSTOM_TOKEN_API
            self.__refresh_path = TO_C_CUSTOM_REFRESH_TOKEN_API
        else:
            self.__login_path = TO_C_SMART_HOME_TOKEN_API
            self.__refresh_path = TO_C_SMART_HOME_REFRESH_TOKEN_API

        self.token_info = XTTokenInfo()
        self.__username = ""
        self.__password = ""
        self.__country_code = ""
        self.__schema = ""

    def __refresh_access_token_if_need(self, path: str):
        if self.is_connect() is False:
            return

        if self.token_info.is_valid() is True:
            return

        if path.startswith(self.__refresh_path):
            return

        self.token_info.access_token = ""

        if self.auth_type == AuthType.CUSTOM:
            response = self.post(
                TO_C_CUSTOM_REFRESH_TOKEN_API + self.token_info.refresh_token
            )
        else:
            response = self.get(
                TO_C_SMART_HOME_REFRESH_TOKEN_API + self.token_info.refresh_token
            )
        self.token_info = XTTokenInfo(response)

    def connect_non_user_specific(self) -> dict[str, Any]:
        response = self.get(
            TO_C_SMART_HOME_TOKEN_API_NEW,
            {
                "grant_type": 1,
            },
        )
        if not response["success"]:
            return response

        # Cache token info.
        self.token_info = XTTokenInfo(response)

        return response

    def connect(
        self,
        username: str = "",
        password: str = "",
        country_code: str = "",
        schema: str = "",
    ) -> dict[str, Any]:
        self.__username = username
        self.__password = password
        self.__country_code = country_code
        self.__schema = schema
        if self.non_user_specific_api:
            return_value = self.connect_non_user_specific()
        else:
            return_value = self.connect_user_specific(
                username=username,
                password=password,
                country_code=country_code,
                schema=schema,
            )
        return return_value

    def connect_user_specific(
        self,
        username: str = "",
        password: str = "",
        country_code: str = "",
        schema: str = "",
    ) -> dict[str, Any]:
        """Connect to Tuya Cloud.

        Args:
            username (str): user name in to C
            password (str): user password in to C
            country_code (str): country code in SMART_HOME
            schema (str): app schema in SMART_HOME

        Returns:
            response: connect response
        """
        if self.auth_type == AuthType.CUSTOM:
            response = self.post(
                TO_C_CUSTOM_TOKEN_API,
                {
                    "username": username,
                    "password": hashlib.sha256(password.encode("utf8"))
                    .hexdigest()
                    .lower(),
                },
            )
        else:
            response = self.post(
                TO_C_SMART_HOME_TOKEN_API,
                {
                    "username": username,
                    "password": hashlib.md5(password.encode("utf8")).hexdigest(),
                    "country_code": country_code,
                    "schema": schema,
                },
            )

        if not response["success"]:
            return response

        # Cache token info.
        self.token_info = XTTokenInfo(response)

        return response

    def reconnect(self) -> bool:
        if (
            self.__username != ""
            and self.__password != ""
            and self.__country_code != ""
        ):
            self.connect(
                self.__username, self.__password, self.__country_code, self.__schema
            )
        return self.is_connect()

    def test_validity(self) -> dict[str, Any]:
        return self.get("/v2.0/cloud/space/child")

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Http Get.

        Requests the server to return specified resources.

        Args:
            path (str): api path
            params (map): request parameter

        Returns:
            response: response body
        """
        return self.__request("GET", path, params, None)

    def post(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Http Post.

        Requests the server to update specified resources.

        Args:
            path (str): api path
            body (map): request body

        Returns:
            response: response body
        """
        return self.__request("POST", path, None, body)

    def put(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Http Put.

        Requires the server to perform specified operations.

        Args:
            path (str): api path
            body (map): request body

        Returns:
            response: response body
        """
        return self.__request("PUT", path, None, body)

    def delete(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Http Delete.

        Requires the server to delete specified resources.

        Args:
            path (str): api path
            params (map): request param

        Returns:
            response: response body
        """
        return self.__request("DELETE", path, params, None)

    def _calculate_sign(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> tuple[str, int]:

        # HTTPMethod
        str_to_sign = method
        str_to_sign += "\n"

        # Content-SHA256
        content_to_sha256 = (
            "" if body is None or len(body.keys()) == 0 else json.dumps(body)
        )

        str_to_sign += (
            hashlib.sha256(content_to_sha256.encode("utf8")).hexdigest().lower()
        )
        str_to_sign += "\n"

        # Header
        str_to_sign += "\n"

        # URL
        str_to_sign += path

        if params is not None and len(params.keys()) > 0:
            str_to_sign += "?"

            params_keys = sorted(params.keys())
            query_builder = "".join(f"{key}={params[key]}&" for key in params_keys)
            str_to_sign += query_builder[:-1]

        # Sign
        t = int(time.time() * 1000)

        message = self.access_id
        if self.token_info.is_valid() is True:
            message += self.token_info.access_token
        message += str(t) + str_to_sign
        sign = (
            hmac.new(
                self.access_secret.encode("utf8"),
                msg=message.encode("utf8"),
                digestmod=hashlib.sha256,
            )
            .hexdigest()
            .upper()
        )
        return sign, t

    def __request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        first_pass: bool = True,
    ) -> dict[str, Any]:
        start_time = datetime.now()
        self.__refresh_access_token_if_need(path)
        access_token = self.token_info.access_token if self.token_info.is_valid() else ""
        sign, t = self._calculate_sign(method, path, params, body)
        headers = {
            "client_id": self.access_id,
            "sign": sign,
            "sign_method": "HMAC-SHA256",
            "access_token": access_token,
            "t": str(t),
            "lang": self.lang,
        }

        if (
            path == self.__login_path
            or path.startswith(TO_C_CUSTOM_REFRESH_TOKEN_API)
            or path.startswith(TO_C_SMART_HOME_REFRESH_TOKEN_API)
        ):
            headers["dev_lang"] = "python"
            headers["dev_version"] = VERSION
            headers["dev_channel"] = self.dev_channel

        response = self.session.request(
            method,
            self.endpoint + path,
            params=params,
            json=body,
            headers=headers,
        )

        if response.ok is False:
            LOGGER.error(
                f"[IOT API]Response error: code={response.status_code}, body={body if body is not None else ''}"
            )
            return {}

        result: dict[str, Any] = response.json()

        # if result.get("success", True) is False:
        time_taken = datetime.now() - start_time
        LOGGER.debug(
            f"[IOT API][{time_taken}]Request: {method} {path} PARAMS: {json.dumps(params, ensure_ascii=False, indent=2) if params is not None else ''} BODY: {json.dumps(body, ensure_ascii=False, indent=2) if body is not None else ''}"
        )
        LOGGER.debug(
            f"[IOT API][{time_taken}]Response: {json.dumps(result, ensure_ascii=False, indent=2)}"
        )

        if result.get("code", -1) == TUYA_ERROR_CODE_TOKEN_INVALID:
            if self.reconnect() is True and first_pass is True:
                return self.__request(method, path, params, body, False)

        return result
