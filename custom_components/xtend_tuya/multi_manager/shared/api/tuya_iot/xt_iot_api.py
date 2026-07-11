from __future__ import annotations
from enum import StrEnum
from typing import Any, cast
import time

class XTAPIIOTTokenInfo:
    """XTAPIIOTTokenInfo"""

    class XTAPIIOTTokenValidity(StrEnum):
        VALID = "valid"
        TOKEN_FETCH_FAILED = "token_fetch_failed"
        MARKED_INVALID = "marked_invalid"
        EXPIRED = "expired"

    def __init__(
        self,
        token_response: dict[str, Any] = {},
    ):
        self._reconnecting = False
        self.update_token(token_response=token_response)
        self._time_mult: int | None = None

    def _convert_time_stamp(self, timestamp: int) -> int:
        """Convert timestamp into the format with milliseconds"""

        if timestamp == 0:
            return timestamp

        if self._time_mult is None:
            current_time = int(time.time() * 1000)
            if current_time / timestamp > 500:
                self._time_mult = 1000
            else:
                self._time_mult = 1

        return timestamp * self._time_mult

    def update_token(self, token_response: dict[str, Any] = {}):
        result = cast(dict[str, Any], token_response.get("result", {}))

        self.expire_time = (
            self._convert_time_stamp(token_response.get("t", 0))
            + result.get("expire", result.get("expire_time", 0)) * 1000
        )
        self._access_token = result.get("access_token", "")
        self._refresh_token = result.get("refresh_token", "")
        self._uid = result.get("uid", "")
        self._success = token_response.get("success", False)
        self._marked_invalid = False

    def is_reconnecting(self) -> bool:
        return self._reconnecting

    def set_reconnecting(self, is_connecting: bool):
        self._reconnecting = is_connecting

    def __repr__(self) -> str:
        return f"TuyaTokenInfo(valid: {self.is_valid()}, expire_time: {self.expire_time}, access_token: {self._access_token}, refresh_token: {self._refresh_token}, uid: {self._uid}, reconnecting: {self._reconnecting})"

    def is_valid(self) -> XTAPIIOTTokenInfo.XTAPIIOTTokenValidity:
        if self._success is False:
            # logger.debug("OpenAPI is_valid: sucess = False")
            return XTAPIIOTTokenInfo.XTAPIIOTTokenValidity.TOKEN_FETCH_FAILED

        if self._marked_invalid:
            # logger.debug("OpenAPI is_valid: marked_invalid = True")
            return XTAPIIOTTokenInfo.XTAPIIOTTokenValidity.MARKED_INVALID

        expiry_check = int(time.time() * 1000) + 5 * 60 * 1000
        if self.expire_time <= expiry_check:
            # logger.debug(
            #     f"OpenAPI is_valid: expiry check: {self.expire_time} <= {expiry_check}: True"
            # )
            return XTAPIIOTTokenInfo.XTAPIIOTTokenValidity.EXPIRED

        return XTAPIIOTTokenInfo.XTAPIIOTTokenValidity.VALID

    def mark_invalid(self) -> None:
        self._marked_invalid = True