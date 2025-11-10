"""Tuya home's api base on asset and device api."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from .asset import TuyaAssetManager
from .device import TuyaDeviceManager
from .infrared import TuyaRemote, TuyaRemoteDevice, TuyaRemoteDeviceKey
from .openapi import TuyaOpenAPI
from .openmq import TuyaOpenMQ
from .tuya_enums import AuthType


class TuyaScene(SimpleNamespace):
    """Tuya Scene.
    Attributes:
        actions(list): scene actions
        enabled(bool): is scene enabled
        name(str): scene name
        scene_id(dict): scene id
        home_id(int): scene home id
    """

    actions: list
    enabled: bool
    name: str
    scene_id: str
    home_id: int


class TuyaHomeManager:
    """Tuya Home Manager."""

    def __init__(
        self, api: TuyaOpenAPI, mq: TuyaOpenMQ, device_manager: TuyaDeviceManager
    ):
        """Init tuya home manager."""
        self.api = api
        self.mq = mq
        self.device_manager = device_manager

    def update_device_cache(self):
        """Update home's devices cache."""
        self.device_manager.device_map.clear()
        if self.api.auth_type == AuthType.CUSTOM:
            device_ids = []
            asset_manager = TuyaAssetManager(self.api)

            self.__query_device_ids(asset_manager, "-1", device_ids)

            # assets = asset_manager.get_asset_list()
            # for asset in assets:
            #     asset_id = asset["asset_id"]
            #     device_ids += asset_manager.get_device_list(asset_id)
            if device_ids:
                self.device_manager.update_device_caches(device_ids)
        elif self.api.auth_type == AuthType.SMART_HOME:
            self.device_manager.update_device_list_in_smart_home()

    def __query_device_ids(
        self, asset_manager: TuyaAssetManager, asset_id: str, device_ids: list
    ) -> list:
        if asset_id != "-1":
            device_ids += asset_manager.get_device_list(asset_id)
        assets = asset_manager.get_asset_list(asset_id)
        for asset in assets:
            self.__query_device_ids(asset_manager, asset["asset_id"], device_ids)
        return device_ids

    def query_scenes(self) -> list:
        """Query home scenes, only in SMART_HOME project type."""
        if self.api.auth_type == AuthType.CUSTOM:
            return []

        response = self.api.get(f"/v1.0/users/{self.api.token_info.uid}/homes")
        if response.get("success", False):
            homes = response.get("result", [])
            scenes = []
            for home in homes:
                home_id = home["home_id"]
                scenes_response = self.api.get(f"/v1.0/homes/{home_id}/scenes")

                if scenes_response.get("success", False):
                    for scene in scenes_response.get("result", []):
                        __tuya_scene = TuyaScene(**scene)
                        __tuya_scene.home_id = home_id
                        scenes.append(__tuya_scene)

            return scenes

        return []

    def trigger_scene(self, home_id: str, scene_id: str) -> dict[str, Any]:
        """Trigger home scene"""
        if self.api.auth_type == AuthType.SMART_HOME:
            return self.api.post(f"/v1.0/homes/{home_id}/scenes/{scene_id}/trigger")

        return {}

    def query_infrared_devices(self) -> list:
        """Query infrared devices, only in SMART_HOME project type."""
        if self.api.auth_type == AuthType.CUSTOM:
            return []

        remote_ids = [
            device_id
            for (device_id, device) in self.device_manager.device_map.items()
            if device.category == "qt"
        ]

        remotes = []
        for remote_id in remote_ids:
            remotes_response = self.api.get(f"/v1.0/infrareds/{remote_id}/remotes")
            if not remotes_response.get("success", False):
                continue

            remote_device_response = remotes_response.get("result", [])

            remote_devices = []
            for remote_device in remote_device_response:
                # Air conditioners not implemented yet ( but it will be in the future )
                if remote_device["category_id"] == "5":
                    continue

                keys_response = self.api.get(
                    f"/v1.0/infrareds/{remote_id}/remotes/{remote_device['remote_id']}/keys"
                )

                if not keys_response.get("success", False):
                    continue

                keys_result = keys_response.get("result")
                key_values = keys_result.get("key_list", [])

                tuya_remote_device_keys = [
                    TuyaRemoteDeviceKey(
                        tuya_key["key"],
                        tuya_key["key_id"],
                        tuya_key["key_name"],
                        tuya_key["standard_key"],
                    )
                    for tuya_key in key_values
                ]
                remote_devices.append(
                    TuyaRemoteDevice(remote_device, tuya_remote_device_keys)
                )

            if remote_devices:
                remotes.append(TuyaRemote(remote_id, remote_devices))

        return remotes

    def trigger_infrared_commands(self, remote_id, device_id, key) -> None:
        """Send infrared commands, only in SMART_HOME project type."""
        if self.api.auth_type == AuthType.CUSTOM:
            return []

        self.api.post(
            f"/v1.0/infrareds/{remote_id}/remotes/{device_id}/command",
            {"key": key},
        )
