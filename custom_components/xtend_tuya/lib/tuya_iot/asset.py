"""Tuya asset api."""
from __future__ import annotations

from typing import Any

from .openapi import TuyaOpenAPI


class TuyaAssetManager:
    """Asset Manager.

    Attributes:
      api: tuya openapi
    """

    def __init__(self, api: TuyaOpenAPI) -> None:
        """Init Tuya asset manager."""
        self.api = api

    ##############################
    # Asset Management
    # https://developer.tuya.com/docs/cloud/industrial-general-asset-management/4872453fec?id=Kag2yom602i40

    def get_device_list(self, asset_id: str) -> list[str]:
        """Get devices by asset_id.

        Args:
          asset_id(str): asset id

        Returns:
          A list of device ids.
        """
        device_id_list: list[str] = []

        has_next = True
        last_row_key = ""
        while has_next:
            response = self.api.get(
                f"/v1.0/iot-02/assets/{asset_id}/devices",
                {"last_row_key": last_row_key, "page_size": 100},
            )
            result = response.get("result", {})
            has_next = result.get("has_next", False)
            last_row_key = result.get("last_row_key", "")
            total_size = result.get("total_size", 0)

            if len(device_id_list) > total_size:  # Error
                raise Exception("get_device_list error, too many devices.")

            for item in result.get("list", []):
                device_id_list.append(item["device_id"])

        return device_id_list

    def get_asset_info(self, asset_id: str) -> dict[str, Any]:
        """Get asset's info.

        Args:
            asset_id(str): asset id

        Returns:
            asset's info
        """
        return self.api.get(f"/v1.0/iot-02/assets/{asset_id}")

    def get_asset_list(self, parent_asset_id: str = "-1") -> list:
        """Get under-nodes unser the current node.

        Args:
            parent_asset_id(str): current node

        Retruns:
            under-nodes
        """
        assets = []
        has_next = True
        last_row_key = ""

        while has_next:
            response = self.api.get(
                f"/v1.0/iot-02/assets/{parent_asset_id}/sub-assets",
                {
                    # "parent_asset_id": parent_asset_id,
                    "asset_id": parent_asset_id,
                    "last_row_key": last_row_key,
                    "page_size": 100,
                },
            )
            result = response.get("result", {})
            has_next = result.get("has_next", False)
            last_row_key = result.get("last_row_key", "")

            for item in result.get("list", []):
                assets.append(item)

        return assets
