from __future__ import annotations

from typing import Any

from tuya_sharing.customerapi import (
    CustomerApi,
)
from ...const import (
    LOGGER,
)

class XTSharingAPI(CustomerApi):
    
    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return_value = super().get(path=path, params=params)
        LOGGER.warning(f"Result of {path} => {return_value}")
        return return_value
    
    def post(self, path: str, params: dict[str, Any] | None = None, body: dict[str, Any] | None = None) -> dict[
        str, Any]:
        return_value = super().post(path=path, params=params, body=body)
        LOGGER.warning(f"Result of {path} => {return_value}")
        return return_value