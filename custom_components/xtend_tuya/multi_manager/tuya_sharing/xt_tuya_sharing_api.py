from __future__ import annotations
from typing import Any
from tuya_sharing.customerapi import (
    CustomerApi,
)


class XTSharingAPI(CustomerApi):

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return_value = super().get(path=path, params=params)
        return return_value

    def post(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return_value = super().post(path=path, params=params, body=body)
        return return_value
