"""Tuya Open API."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, cast

import requests

from .openlogging import logger
from .tuya_enums import AuthType
from .version import VERSION

TUYA_ERROR_CODE_TOKEN_INVALID = 1010
TUYA_ERROR_SIGN_INVALID = 1004

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

    def __init__(
        self,
        token_response: dict[str, Any] = {},
        shared_token_info: TuyaTokenInfo | None = None,
    ):
        """Init TuyaTokenInfo."""
        self.shared_token_info = shared_token_info
        self.reconnecting = False
        self.update_token(token_response=token_response)

    def update_token(self, token_response: dict[str, Any] = {}):
        result = cast(dict[str, Any], token_response.get("result", {}))

        self.expire_time = (
            token_response.get("t", 0)
            + result.get("expire", result.get("expire_time", 0)) * 1000
        )
        self.access_token = result.get("access_token", "")
        self.refresh_token = result.get("refresh_token", "")
        self.uid = result.get("uid", "")
        self.success = token_response.get("success", False)
        self.marked_invalid = False
        # logger.debug(f"Refreshing TuyaTokenInfo: {token_response} => {self}")
        if self.shared_token_info is not None:
            self.shared_token_info.update_token(token_response=token_response)

    def is_reconnecting(self) -> bool:
        if (
            self.shared_token_info is not None
            and self.shared_token_info.is_reconnecting()
        ):
            return True
        return self.reconnecting

    def set_reconnecting(self, is_connecting: bool):
        self.reconnecting = is_connecting
        if self.shared_token_info is not None:
            self.shared_token_info.set_reconnecting(
                is_connecting=is_connecting,
            )

    def __repr__(self) -> str:
        return f"TuyaTokenInfo(valid: {self.is_valid()}, expire_time: {self.expire_time}, access_token: {self.access_token}, refresh_token: {self.refresh_token}, uid: {self.uid})"

    def is_valid(self) -> bool:
        if self.success is False:
            # logger.debug("OpenAPI is_valid: sucess = False")
            return False

        if self.marked_invalid:
            # logger.debug("OpenAPI is_valid: marked_invalid = True")
            return False

        expiry_check = int(time.time() * 1000) + 5 * 60 * 1000
        if self.expire_time <= expiry_check:
            # logger.debug(
            #     f"OpenAPI is_valid: expiry check: {self.expire_time} <= {expiry_check}: True"
            # )
            return False

        return True

    def mark_invalid(self) -> None:
        self.marked_invalid = True


class TuyaOpenAPI:
    """Open Api.

    Typical usage example:

    openapi = TuyaOpenAPI(ENDPOINT, ACCESS_ID, ACCESS_KEY)
    """

    def __init__(
        self,
        endpoint: str,
        access_id: str,
        access_secret: str,
        shared_token_info: TuyaTokenInfo,
        auth_type: AuthType = AuthType.SMART_HOME,
        lang: str = "en",
        non_user_specific_api: bool = False,
    ) -> None:
        """Init TuyaOpenAPI."""
        self.session = requests.session()

        self.endpoint = endpoint
        self.access_id = access_id
        self.access_secret = access_secret
        self.lang = lang

        self.auth_type = auth_type
        if self.auth_type == AuthType.CUSTOM:
            if non_user_specific_api is True:
                self.__login_path = TO_C_CUSTOM_REFRESH_TOKEN_API
            else:
                self.__login_path = TO_C_CUSTOM_TOKEN_API
            self.__refresh_path = TO_C_CUSTOM_REFRESH_TOKEN_API
        else:
            if non_user_specific_api is True:
                self.__login_path = TO_C_SMART_HOME_REFRESH_TOKEN_API
            else:
                self.__login_path = TO_C_SMART_HOME_TOKEN_API
            self.__refresh_path = TO_C_SMART_HOME_REFRESH_TOKEN_API

        self.non_user_specific_api = non_user_specific_api
        self.token_info = TuyaTokenInfo()  # (shared_token_info=shared_token_info)
        self.shared_token = shared_token_info

        self.dev_channel: str = ""

        self.__username = ""
        self.__password = ""
        self.__country_code = ""
        self.__schema = ""

    def report_message(self, method: str, message: str, stack_info: bool = False):
        method_call = getattr(logger, method, None)
        if method_call is not None and callable(method_call):
            method_call(msg=message, stack_info=stack_info)

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

    def __refresh_access_token_if_need(self, path: str, first_pass: bool):
        # logger.debug(f"Check if need to refresh access token. {self.token_info}")
        if first_pass is False:
            # logger.debug("Not the first pass, do not refresh access token again.")
            return
        if self.token_info.is_valid() is True:
            # logger.debug("Access token is valid, no need to refresh.")
            return

        if path.startswith(self.__refresh_path) or path.startswith(self.__login_path):
            # logger.debug("Already requesting refresh token, no need to refresh again.")
            return

        if self.reconnect(no_loop=False):
            # logger.warning(f"Successfully reconnected: {self.token_info}")
            pass

    def set_dev_channel(self, dev_channel: str):
        """Set dev channel."""
        self.dev_channel = dev_channel

    def test_validity(self) -> bool:
        response = self.get("/v2.0/cloud/space/child")
        if response.get("success", False):
            return True
        else:
            logger.error(
                f"Test API validity failed: AuthType: {self.auth_type} <=> {response}"
            )
        return False

    def connect(
        self,
        username: str = "",
        password: str = "",
        country_code: str = "",
        schema: str = "",
    ) -> dict[str, Any]:
        self.token_info.set_reconnecting(is_connecting=True)
        if self.non_user_specific_api:
            return_value = self.connect_non_user_specific()
        else:
            return_value = self.connect_user_specific(
                username=username,
                password=password,
                country_code=country_code,
                schema=schema,
            )
        self.token_info.set_reconnecting(is_connecting=False)
        return return_value

    def connect_non_user_specific(self) -> dict[str, Any]:
        if self.auth_type == AuthType.CUSTOM:
            response = self.get(
                TO_C_CUSTOM_REFRESH_TOKEN_API,
                {
                    "grant_type": 1,
                },
            )
        else:
            response = self.get(
                TO_C_SMART_HOME_REFRESH_TOKEN_API,
                {
                    "grant_type": 1,
                },
            )
        if not response["success"]:
            return response

        # Cache token info.
        self.token_info.update_token(response)

        return response

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
        self.__username = username
        self.__password = password
        self.__country_code = country_code
        self.__schema = schema

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

        if not response.get("success", False):
            return response

        # Cache token info.
        self.token_info.update_token(response)

        return response

    def is_token_valid(self) -> bool:
        """Is connect to tuya cloud."""
        return self.token_info.is_valid()

    def reconnect(self, no_loop: bool = False) -> bool:
        if (
            self.__username != ""
            and self.__password != ""
            and self.__country_code != ""
            and self.token_info.is_reconnecting() is False
        ):
            self.connect(
                self.__username, self.__password, self.__country_code, self.__schema
            )
        elif self.token_info.is_reconnecting() is True and no_loop is False:
            wait_time = 0.2
            loop_pass = 0
            # logger.debug("Already connecting to tuya cloud, wait for it to finish.")
            while self.token_info.is_reconnecting() is True:
                time.sleep(wait_time)
                loop_pass += 1
            if self.token_info.is_valid() is False:
                return self.reconnect(no_loop=True)
            # logger.debug(
            #     f"Waited {wait_time * loop_pass} seconds for reconnection."
            # )
        return self.is_token_valid()

    def __request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        first_pass: bool = True,
    ) -> dict[str, Any]:
        start_time = time.time()
        self.__refresh_access_token_if_need(path, first_pass)
        access_token = (
            self.token_info.access_token if self.token_info.is_valid() else ""
        )
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

        result: dict[str, Any] = response.json()

        time_taken = time.time() - start_time

        if response.ok is False or result.get("success", True) is False:
            self.report_message(
                "debug",
                f"[IOT API][{time_taken}]Request: {method} {path} PARAMS: {json.dumps(params, ensure_ascii=False, indent=2) if params is not None else ''} BODY: {json.dumps(body, ensure_ascii=False, indent=2) if body is not None else ''}, first_pass={first_pass}, access_token={access_token}"
            )
            self.report_message(
                "debug",
                f"[IOT API][{time_taken}]Response: {json.dumps(result, ensure_ascii=False, indent=2)}",
                stack_info=True,
            )
            pass
        if first_pass is False:
            self.report_message(
                "warning",
                f"[IOT API][{time_taken}]SECOND PASS Request: {method} {path} PARAMS: {json.dumps(params, ensure_ascii=False, indent=2) if params is not None else ''} BODY: {json.dumps(body, ensure_ascii=False, indent=2) if body is not None else ''}, first_pass={first_pass}, access_token={access_token}",
            )
            self.report_message(
                "warning",
                f"[IOT API][{time_taken}]SECOND PASS Response: {json.dumps(result, ensure_ascii=False, indent=2)}",
                stack_info=True,
            )
        else:
            # logger.debug(
            #     f"[IOT API][{time_taken}]Request: {method} {path} PARAMS: {json.dumps(params, ensure_ascii=False, indent=2) if params is not None else ''} BODY: {json.dumps(body, ensure_ascii=False, indent=2) if body is not None else ''}"
            # )
            # logger.debug(
            #     f"[IOT API][{time_taken}]Response: {json.dumps(result, ensure_ascii=False, indent=2)}"
            # )
            pass

        if result.get("code", -1) in [
            TUYA_ERROR_CODE_TOKEN_INVALID,
            TUYA_ERROR_SIGN_INVALID,
        ]:
            self.token_info.mark_invalid()
            if (
                first_pass is True
                and path.startswith(self.__login_path) is False
                and path.startswith(self.__refresh_path) is False
            ):
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
