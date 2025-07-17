from __future__ import annotations
from typing import Any
from tuya_sharing.customerapi import (
    CustomerApi,
)


class XTSharingAPI(CustomerApi):

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return_value = super().get(path=path, params=params)
        # LOGGER.warning(f"GET: {path} => {json.dumps(params, separators=(',', ':')) if params else None} => {return_value}")
        return return_value

    def post(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return_value = super().post(path=path, params=params, body=body)
        # LOGGER.warning(f"POST: {path} => {json.dumps(params, separators=(',', ':')) if params else None} <=> {json.dumps(body, separators=(',', ':')) if body else None} => {return_value}")
        return return_value
