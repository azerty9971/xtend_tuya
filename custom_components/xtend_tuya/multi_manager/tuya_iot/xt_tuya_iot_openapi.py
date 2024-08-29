from __future__ import annotations

from typing import Any

from tuya_iot.openapi import (
    TuyaOpenAPI,
    AuthType,
    TO_C_CUSTOM_REFRESH_TOKEN_API,
    TO_C_SMART_HOME_REFRESH_TOKEN_API,
    TUYA_ERROR_CODE_TOKEN_INVALID,
)

from ...const import (
    LOGGER,
)

class XTIOTOpenAPI(TuyaOpenAPI):
    def __init__(
        self,
        endpoint: str,
        access_id: str,
        access_secret: str,
        auth_type: AuthType = AuthType.SMART_HOME,
        lang: str = "en",
    ) -> None:
        super().__init__(endpoint=endpoint, access_id=access_id, access_secret=access_secret, auth_type=auth_type, lang=lang)
        self.connect_response = None
    
    def connect(
        self,
        username: str = "",
        password: str = "",
        country_code: str = "",
        schema: str = "",
    ) -> dict[str, Any]:
        self.connect_response = super().connect(username=username, password=password, country_code=country_code, schema=schema)
        LOGGER.warning(f"Connect response: {self.connect_response}")
        return self.connect_response
    
    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        normal_result = super().get(path=path, params=params)
        LOGGER.warning(f"get1 : {path} <=> {params} <=> {normal_result}")
        if ( 
            normal_result.get("code", -1) == TUYA_ERROR_CODE_TOKEN_INVALID and
            self.connect_response is not None and
            (
                path.startswith(TO_C_CUSTOM_REFRESH_TOKEN_API) or
                path.startswith(TO_C_SMART_HOME_REFRESH_TOKEN_API)
            )
        ):
            normal_result = self.connect_response
            self.connect_response = None
        LOGGER.warning(f"get2: {normal_result}")
        return normal_result

    def post(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        normal_result = super().post(path=path, body=body)
        LOGGER.warning(f"post1: {path} <=> {body} <=> {normal_result}")
        if ( 
            normal_result.get("code", -1) == TUYA_ERROR_CODE_TOKEN_INVALID and
            self.connect_response is not None and
            (
                path.startswith(TO_C_CUSTOM_REFRESH_TOKEN_API) or
                path.startswith(TO_C_SMART_HOME_REFRESH_TOKEN_API)
            )
        ):
            normal_result = self.connect_response
            self.connect_response = None
        LOGGER.warning(f"post2: {normal_result}")
        return normal_result