"""Tuya Open API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.xtend_tuya.lib.tuya_iot.openapi import TuyaTokenInfo
from custom_components.xtend_tuya.lib.tuya_iot.tuya_enums import AuthType
from ....lib.tuya_iot import (
    TuyaOpenAPI,
)

from ....const import (
    XTDeviceWatcherSpecialDevice,
    XTDeviceWatcherCategory,
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

    def report_message(self, method: str, message: str, stack_info: bool = False):
        if self.multi_manager:
            self.multi_manager.device_watcher.report_message(
                XTDeviceWatcherSpecialDevice.NOT_LINKED_TO_A_DEVICE,
                message,
                XTDeviceWatcherCategory.IOT_API,
            )
        else:
            return super().report_message(method, message, stack_info)
