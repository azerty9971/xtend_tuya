"""Tuya Open API."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import requests

from tuya_iot.tuya_enums import AuthType
from tuya_iot.version import VERSION
from ...const import (
    LOGGER,  # noqa: F401
)

TUYA_ERROR_CODE_TOKEN_INVALID = 1010

TO_C_CUSTOM_REFRESH_TOKEN_API = "/v1.0/iot-03/users/token/"
TO_C_SMART_HOME_REFRESH_TOKEN_API = "/v1.0/token/"

TO_C_CUSTOM_TOKEN_API = "/v1.0/iot-03/users/login"
TO_C_SMART_HOME_TOKEN_API = "/v1.0/iot-01/associated-users/actions/authorized-login"


class TuyaTokenInfo:
    """Tuya token info.

    Attributes:
        access_token: Access token.
        expire_time: Valid period in seconds.
        refresh_token: Refresh token.
        uid: Tuya user ID.
        platform_url: user region platform url
    """

    def __init__(self, token_response: dict[str, Any] = None):
        """Init TuyaTokenInfo."""
        result = token_response.get("result", {})

        self.expire_time = (
            token_response.get("t", 0)
            + result.get("expire", result.get("expire_time", 0)) * 1000
        )
        self.access_token = result.get("access_token", "")
        self.refresh_token = result.get("refresh_token", "")
        self.uid = result.get("uid", "")
        self.platform_url = result.get("platform_url", "")


class XTIOTOpenAPI:
    """Open Api.

    Typical usage example:

    openapi = TuyaOpenAPI(ENDPOINT, ACCESS_ID, ACCESS_KEY)
    """

    def __init__(
        self,
        endpoint: str,
        access_id: str,
        access_secret: str,
        auth_type: AuthType = AuthType.SMART_HOME,
        lang: str = "en",
    ) -> None:
        """Init TuyaOpenAPI."""
        self.session = requests.session()

        self.endpoint = endpoint
        self.access_id = access_id
        self.access_secret = access_secret
        self.lang = lang
        self.connecting: bool = False

        self.auth_type = auth_type
        if self.auth_type == AuthType.CUSTOM:
            self.__login_path = TO_C_CUSTOM_TOKEN_API
        else:
            self.__login_path = TO_C_SMART_HOME_TOKEN_API

        self.token_info: TuyaTokenInfo = None

        self.dev_channel: str = ""

        self.__username = ""
        self.__password = ""
        self.__country_code = ""
        self.__schema = ""

    # https://developer.tuya.com/docs/iot/open-api/api-reference/singnature?id=Ka43a5mtx1gsc
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
        if self.token_info is not None:
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

    def __refresh_access_token_if_need(self, path: str):
        if self.is_connect() is False:
            return

        if path.startswith(self.__login_path):
            return

        # should use refresh token?
        now = int(time.time() * 1000)
        expired_time = self.token_info.expire_time

        if expired_time - 60 * 1000 > now:  # 1min
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

        self.token_info = TuyaTokenInfo(response)

    def set_dev_channel(self, dev_channel: str):
        """Set dev channel."""
        self.dev_channel = dev_channel

    def connect(
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
        self.__username = username
        self.__password = password
        self.__country_code = country_code
        self.__schema = schema
        self.connecting = True
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
        self.connecting = False
        if not response["success"]:
            return response

        # Cache token info.
        self.token_info = TuyaTokenInfo(response)

        return response

    def is_connect(self) -> bool:
        """Is connect to tuya cloud."""
        if (
            self.token_info is None
            and not self.connecting
            and self.__username 
            and self.__password
            and self.__country_code
        ):
            connect_result = self.connect(
                self.__username, self.__password, self.__country_code, self.__schema
            )
            LOGGER.debug(f"Trying to connect: {connect_result}")
        return self.token_info is not None and len(self.token_info.access_token) > 0

    def __request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        first_pass: bool = True
    ) -> dict[str, Any]:

        self.__refresh_access_token_if_need(path)

        access_token = self.token_info.access_token if self.token_info else ""
        sign, t = self._calculate_sign(method, path, params, body)
        headers = {
            "client_id": self.access_id,
            "sign": sign,
            "sign_method": "HMAC-SHA256",
            "access_token": access_token,
            "t": str(t),
            "lang": self.lang,
        }

        if path == self.__login_path or \
            path.startswith(TO_C_CUSTOM_REFRESH_TOKEN_API) or\
            path.startswith(TO_C_SMART_HOME_REFRESH_TOKEN_API):
            headers["dev_lang"] = "python"
            headers["dev_version"] = VERSION
            headers["dev_channel"] = self.dev_channel

        """ LOGGER.debug(
            f"Request: method = {method}, \
                url = {self.endpoint + path},\
                params = {params},\
                body = {body},\
                t = {int(time.time()*1000)}"
        ) """

        for _ in range(10):
            try:
                response = self.session.request(
                    method, self.endpoint + path, params=params, json=body, headers=headers
                )
                break
            except Exception:
                time.sleep(2)

        if response.ok is False:
            LOGGER.error(
                f"Response error: code={response.status_code}, body={response.body}"
            )
            return None

        result = response.json()

        """ LOGGER.debug(
            f"Response: {json.dumps(result, ensure_ascii=False, indent=2)}"
        ) """

        if result.get("code", -1) == TUYA_ERROR_CODE_TOKEN_INVALID:
            self.token_info = None
            self.connect(
                self.__username, self.__password, self.__country_code, self.__schema
            )
            if first_pass:
                return self.__request(method, path, params, body, False)

        return result

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
