"""Tuya Open API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import time

from custom_components.xtend_tuya.lib.tuya_iot.openapi import TuyaTokenInfo
from custom_components.xtend_tuya.lib.tuya_iot.tuya_enums import AuthType
from ....lib.tuya_iot import (
    TuyaOpenAPI,
)

from ....const import (
    XTDeviceWatcherSpecialDevice,
    XTDeviceWatcherCategory,
    LOGGER,
)

if TYPE_CHECKING:
    from ...multi_manager import (
        MultiManager,
    )


class XTIOTOpenAPI(TuyaOpenAPI):

    def __init__(
        self,
        endpoint: str,
        access_id: str,
        access_secret: str,
        shared_token_info: TuyaTokenInfo,
        auth_type: AuthType = AuthType.SMART_HOME,
        lang: str = "en",
        non_user_specific_api: bool = False,
        multi_manager: MultiManager | None = None,
    ) -> None:
        self.multi_manager = multi_manager
        super().__init__(
            endpoint,
            access_id,
            access_secret,
            shared_token_info,
            auth_type,
            lang,
            non_user_specific_api,
        )
        # self.request_log: dict[str, dict[str, Any]] = {}
        self.request_log: list[str] = []

    def report_message(self, method: str, message: str, stack_info: bool = False):
        if self.multi_manager:
            self.multi_manager.device_watcher.report_message(
                dev_id=XTDeviceWatcherSpecialDevice.NOT_LINKED_TO_A_DEVICE,
                message=message,
                category=XTDeviceWatcherCategory.IOT_API,
                print_stack=stack_info,
                method=method,
            )
        else:
            return super().report_message(method, message, stack_info)

    def _register_request_in_log(self, method: str, path:str, params: dict[str, Any] | None, caching_allowed: bool, elapsed_time: float, group_key: str | None):
        self.request_log.append(f"{method} {path} | {caching_allowed} | {elapsed_time}")

    def get_request_log(self) -> list[str]:
        return self.request_log

    def print_request_log(self):
        request_string: str = ""
        for request in self.get_request_log():
            request_string += f"{request}\n\r"
        LOGGER.debug(f"print_request_log\n\r{request_string}")

    def get(self, path: str, params: dict[str, Any] | None = None, allow_caching: bool = False, group_key: str | None = None) -> dict[str, Any]:
        start = time.perf_counter()

        to_return = super().get(path=path, params=params)

        elapsed = time.perf_counter() - start
        self._register_request_in_log(method="GET", path=path, params=params, caching_allowed=allow_caching, elapsed_time=elapsed, group_key=group_key)
        return to_return

    def post(self, path: str, body: dict[str, Any] | None = None, group_key: str | None = None) -> dict[str, Any]:
        start = time.perf_counter()

        to_return = super().post(path=path, body=body)

        elapsed = time.perf_counter() - start
        self._register_request_in_log(method="POST", path=path, params=body, caching_allowed=False, elapsed_time=elapsed, group_key=group_key)
        return to_return
        
