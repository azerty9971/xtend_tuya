from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Literal, Any
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from webrtc_models import (
    RTCIceCandidateInit,
)
from homeassistant.components.camera.webrtc import WebRTCSendMessage
from ..shared_classes import (
    XTConfigEntry,
    XTDeviceMap,
)
import custom_components.xtend_tuya.multi_manager.multi_manager as mm
import custom_components.xtend_tuya.multi_manager.shared.shared_classes as shared
from ....const import (
    DOMAIN,
    LOGGER,
    XTDeviceSourcePriority,
)
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
)


class XTDeviceManagerInterface(ABC):

    @abstractmethod
    def get_type_name(self) -> str:
        pass

    @abstractmethod
    def is_type_initialized(self) -> bool:
        return False

    @abstractmethod
    async def setup_from_entry(
        self,
        hass: HomeAssistant,
        config_entry: XTConfigEntry,
        multi_manager: mm.MultiManager,
    ) -> bool:
        pass

    @abstractmethod
    def update_device_cache(self):
        pass

    @abstractmethod
    def get_available_device_maps(self) -> list[XTDeviceMap]:
        pass

    def remove_device_listeners(self):
        pass

    def refresh_mq(self):
        pass

    def unload(self):
        pass

    @abstractmethod
    def on_message(self, msg: dict):
        pass

    @abstractmethod
    def query_scenes(self) -> list:
        pass

    @abstractmethod
    def get_device_stream_allocate(
        self, device_id: str, stream_type: Literal["flv", "hls", "rtmp", "rtsp"]
    ) -> Optional[str]:
        pass

    def send_lock_unlock_command(self, device: shared.XTDevice, lock: bool) -> bool:
        return False

    @abstractmethod
    def get_device_registry_identifiers(self) -> list:
        return []

    @abstractmethod
    def get_domain_identifiers_of_device(self, device_id: str) -> list:
        pass

    def on_update_device(self, device: shared.XTDevice) -> list[str] | None:
        return None

    def on_add_device(self, device: shared.XTDevice) -> list[str] | None:
        return None

    def on_mqtt_stop(self):
        pass

    def on_post_setup(self):
        pass

    def get_platform_descriptors_to_merge(self, platform: Platform) -> Any:
        pass

    def get_platform_descriptors_to_exclude(self, platform: Platform) -> Any:
        pass

    def send_commands(self, device_id: str, commands: list[dict[str, Any]]) -> bool:
        return False

    @abstractmethod
    def convert_to_xt_device(
        self, device: Any, device_source_priority: XTDeviceSourcePriority | None = None
    ) -> shared.XTDevice:
        pass

    def inform_device_has_an_entity(self, device_id: str):
        for device_map in self.get_available_device_maps():
            if device_id in device_map:
                device_map[device_id].set_up = True

    def call_api(
        self, method: str, url: str, payload: str | None
    ) -> dict[str, Any] | None:
        pass

    def trigger_scene(self, home_id: str, scene_id: str) -> bool:
        return False

    def get_webrtc_sdp_answer(
        self, device_id: str, session_id: str, sdp_offer: str, channel: str
    ) -> str | None:
        return None

    def get_webrtc_ice_servers(
        self, device_id: str, session_id: str | None, format: str, hass: HomeAssistant
    ) -> str | None:
        return None

    def get_webrtc_exchange_debug(self, session_id: str) -> str | None:
        return None

    def delete_webrtc_session(self, device_id: str, session_id: str) -> str | None:
        return None

    def send_webrtc_trickle_ice(
        self, device_id: str, session_id: str, candidate: str
    ) -> str | None:
        return None

    async def async_handle_async_webrtc_offer(
        self,
        offer_sdp: str,
        session_id: str,
        send_message: WebRTCSendMessage,
        device: shared.XTDevice,
        hass: HomeAssistant,
    ) -> None:
        return None

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit, device: shared.XTDevice
    ) -> None:
        return None

    def on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit, device: shared.XTDevice
    ) -> None:
        return None

    def set_webrtc_resolution(
        self, session_id: str, resolution: int, device: shared.XTDevice
    ) -> None:
        return None

    def on_webrtc_close_session(self, session_id: str, device: shared.XTDevice) -> None:
        return None

    async def async_get_webrtc_ice_servers(
        self, device: shared.XTDevice, format: str, hass: HomeAssistant
    ) -> tuple[str, dict] | None:
        return None

    async def on_loading_finalized(
        self,
        hass: HomeAssistant,
        config_entry: XTConfigEntry,
        multi_manager: mm.MultiManager,
    ) -> None:
        return None

    async def raise_issue(
        self,
        hass: HomeAssistant,
        config_entry: XTConfigEntry,
        is_fixable: bool,
        severity: IssueSeverity,
        translation_key: str,
        translation_placeholders: dict[str, Any],
        learn_more_url: str | None = None,
    ):
        try:
            async_create_issue(
                hass=hass,
                domain=DOMAIN,
                issue_domain=DOMAIN,
                issue_id=f"{config_entry.entry_id}_{translation_key}",
                is_fixable=is_fixable,
                severity=severity,
                translation_key=translation_key,
                translation_placeholders=translation_placeholders,
                learn_more_url=learn_more_url,
            )
        except Exception as e:
            # Prevent failure for any reason on this method
            LOGGER.error(f"Exception raised during raise_issue: {e}")
