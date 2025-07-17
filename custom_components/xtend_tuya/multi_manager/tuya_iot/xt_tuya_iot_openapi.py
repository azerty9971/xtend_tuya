"""Tuya Open API."""

from __future__ import annotations
import time
from typing import Any
import requests
from tuya_iot import (
    TuyaOpenAPI,
)
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
TO_C_SMART_HOME_TOKEN_API_NEW = "/v1.0/token"


class TuyaTokenInfo:
    """Tuya token info.

    Attributes:
        access_token: Access token.
        expire_time: Valid period in seconds.
        refresh_token: Refresh token.
        uid: Tuya user ID.
        platform_url: user region platform url
    """

    def __init__(self, token_response: dict[str, Any]):
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


class XTIOTOpenAPI(TuyaOpenAPI):
    """Open Api.

    Typical usage example:

    openapi = TuyaOpenAPI(ENDPOINT, ACCESS_ID, ACCESS_KEY)
    """

    token_info: TuyaTokenInfo | None = None
    connecting: bool = False

    def __init__(
        self,
        endpoint: str,
        access_id: str,
        access_secret: str,
        auth_type: AuthType = AuthType.SMART_HOME,
        lang: str = "en",
        non_user_specific_api: bool = False,
    ) -> None:
        """Init TuyaOpenAPI."""
        super().__init__(
            endpoint=endpoint,
            access_id=access_id,
            access_secret=access_secret,
            auth_type=auth_type,
            lang=lang,
        )

        self.connecting = False
        self.non_user_specific_api = non_user_specific_api
        if self.auth_type == AuthType.CUSTOM:
            self.__login_path = TO_C_CUSTOM_TOKEN_API
            self.__refresh_path = TO_C_CUSTOM_REFRESH_TOKEN_API
        else:
            self.__login_path = TO_C_SMART_HOME_TOKEN_API
            self.__refresh_path = TO_C_SMART_HOME_REFRESH_TOKEN_API

        self.token_info = None
        self.__username = ""
        self.__password = ""
        self.__country_code = ""
        self.__schema = ""

    def __refresh_access_token_if_need(self, path: str):
        # LOGGER.debug(f"[API]Calling __refresh_access_token_if_need")
        if self.is_connect() is False:  # and self.reconnect() is False:
            return

        if self.token_info is None:
            return

        if path.startswith(self.__refresh_path):
            # LOGGER.debug(f"[API]__refresh_access_token_if_need path starts with refresh path")
            return

        # should use refresh token?
        now = int(time.time() * 1000)
        expired_time = self.token_info.expire_time

        if expired_time - 60 * 1000 > now:  # 1min
            # LOGGER.debug(f"[API]__refresh_access_token_if_need token is not old enough ({expired_time - 60 * 1000} > {now})")
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
        # LOGGER.debug(f"[API]__refresh_access_token_if_need response: {response}")
        self.token_info = TuyaTokenInfo(response)

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
        self.token_info = TuyaTokenInfo(response)

        return response

    def connect(
        self,
        username: str = "",
        password: str = "",
        country_code: str = "",
        schema: str = "",
    ) -> dict[str, Any]:
        self.connecting = True
        self.__username = username
        self.__password = password
        self.__country_code = country_code
        self.__schema = schema
        # LOGGER.debug(f"[API]Calling connect")
        if self.non_user_specific_api:
            return_value = self.connect_non_user_specific()
        else:
            return_value = super().connect(
                username=username,
                password=password,
                country_code=country_code,
                schema=schema,
            )
        self.connecting = False
        return return_value

    def reconnect(self) -> bool:
        # LOGGER.debug(f"[API]Calling reconnect (connecting: {self.connecting})")
        if (
            not self.connecting
            and self.__username
            and self.__password
            and self.__country_code
        ):
            self.token_info = None  # type: ignore
            self.connect(
                self.__username, self.__password, self.__country_code, self.__schema
            )
        return self.is_connect()

    def is_connect(self) -> bool:
        """Is connect to tuya cloud."""
        ret_val = super().is_connect()
        # LOGGER.debug(f"[API]is_connect = {ret_val}")
        return ret_val

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

    def __request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        first_pass: bool = True,
    ) -> dict[str, Any]:

        self.__refresh_access_token_if_need(path)
        # LOGGER.debug(f"[API]Requesting: {method} {path} (first_pass={first_pass})")
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

        if (
            path == self.__login_path
            or path.startswith(TO_C_CUSTOM_REFRESH_TOKEN_API)
            or path.startswith(TO_C_SMART_HOME_REFRESH_TOKEN_API)
        ):
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

        response = requests.Response()
        for _ in range(10):
            try:
                response = self.session.request(
                    method,
                    self.endpoint + path,
                    params=params,
                    json=body,
                    headers=headers,
                )
                break
            except Exception as e:
                LOGGER.debug(
                    f"[API]Exception in request, waiting for 2 seconds and retrying {e}"
                )
                time.sleep(2)

        if response.ok is False:
            LOGGER.error(
                f"[API]Response error: code={response.status_code}, body={body if body is not None else ""}"
            )
            return {}

        result: dict[str, Any] = response.json()

        # LOGGER.debug(
        #     f"[API]Response: {json.dumps(result, ensure_ascii=False, indent=2)}"
        # )

        if result.get("code", -1) == TUYA_ERROR_CODE_TOKEN_INVALID:
            self.reconnect()
            if first_pass:
                return self.__request(method, path, params, body, False)

        return result
