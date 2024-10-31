from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Literal, Any

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from ..shared_classes import (
    XTConfigEntry,
)
from ..device import (
    XTDevice,
)
from ...multi_manager import (
    MultiManager,
)

class XTDeviceManagerInterface(ABC):

    @abstractmethod
    def get_type_name(self) -> str:
        return None

    @abstractmethod
    async def setup_from_entry(self, hass: HomeAssistant, config_entry: XTConfigEntry, multi_manager: MultiManager) -> XTDeviceManagerInterface:
        return None

    @abstractmethod
    def update_device_cache(self):
        pass

    @abstractmethod
    def get_available_device_maps(self) -> list[dict[str, XTDevice]]:
        pass

    def remove_device_listeners(self):
        pass

    def refresh_mq(self):
        pass

    def unload(self):
        pass
    
    @abstractmethod
    def on_message(self, msg: str):
        pass

    def query_scenes(self) -> list:
        pass

    def get_device_stream_allocate(
            self, device_id: str, stream_type: Literal["flv", "hls", "rtmp", "rtsp"]
    ) -> Optional[str]:
        pass

    def send_lock_unlock_command(
            self, device_id: str, lock: bool
    ) -> bool:
        return False
    
    @abstractmethod
    def get_device_registry_identifiers(self) -> list:
        return []
    
    @abstractmethod
    def get_domain_identifiers_of_device(self, device_id: str) -> list:
        pass

    def on_update_device(self, device: XTDevice) -> list[str] | None:
        return None

    def on_add_device(self, device: XTDevice) -> list[str] | None:
        return None

    def on_mqtt_stop(self):
        pass

    def on_post_setup(self):
        pass

    def get_platform_descriptors_to_merge(self, platform: Platform) -> Any:
        pass

    def send_commands(self, device_id: str, commands: list[dict[str, Any]]):
        pass

    def get_devices_from_device_id(self, device_id: str) -> list[XTDevice] | None:
        return_list = []
        device_maps = self.get_available_device_maps()
        for device_map in device_maps:
            if device_id in device_map:
                return_list.append(device_map[device_id])
        return return_list
    
    @abstractmethod
    def convert_to_xt_device(self, Any) -> XTDevice:
        pass

    def inform_device_has_an_entity(self, device_id: str):
        for device_map in self.get_available_device_maps():
            if device_id in device_map:
                device_map[device_id].set_up = True
    
    def call_api(self, method: str, url: str, payload: str) -> str | None:
        pass

    def trigger_scene(self, home_id: str, scene_id: str) -> False:
        return False
    
    def get_webrtc_sdp_answer(self, device_id: str, session_id: str, sdp_offer: str, channel: str) -> str | None:
        return None
    
    def get_webrtc_ice_servers(self, device_id: str, session_id: str, format: str) -> str | None:
        return None
    
    def get_webrtc_exchange_debug(self, session_id: str) -> str | None:
        return None
    
    def delete_webrtc_session(self, device_id: str, session_id: str) -> str | None:
        return None
    
    def send_webrtc_trickle_ice(self, device_id: str, session_id: str, candidate: str) -> str | None:
        return None