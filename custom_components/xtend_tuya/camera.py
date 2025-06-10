"""Support for XT cameras."""

from __future__ import annotations

import asyncio

from webrtc_models import (
    RTCIceCandidateInit,
)

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.camera.webrtc import WebRTCSendMessage

from .util import (
    append_lists
)

from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
    XTDeviceManagerInterface,
)

from .const import TUYA_DISCOVERY_NEW, LOGGER, XTDPCode, MESSAGE_SOURCE_TUYA_IOT
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaCameraEntity,
)
from .entity import (
    XTEntity,
)

# All descriptions can be found here:
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
CAMERAS: tuple[str, ...] = (
    "jtmspro",
    "videolock",
    "sp",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya cameras dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    merged_categories = CAMERAS
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.CAMERA):
        merged_categories = tuple(append_lists(list(merged_categories), new_descriptor))

    @callback
    def async_discover_device(device_map) -> None:
        """Discover and add a discovered Tuya camera."""
        if hass_data.manager is None:
            return
        entities: list[XTCameraEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if device.category in merged_categories:
                    if XTCameraEntity.should_entity_be_added(hass, device, hass_data.manager):
                        entities.append(XTCameraEntity(device, hass_data.manager, hass))

        async_add_entities(entities)

    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTCameraEntity(XTEntity, TuyaCameraEntity):
    """XT Camera Entity."""

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        hass: HomeAssistant,
    ) -> None:
        """Init XT Camera."""
        super(XTCameraEntity, self).__init__(device, device_manager)
        super(XTEntity, self).__init__(device, device_manager) # type: ignore
        self.device = device
        self.device_manager = device_manager
        self.iot_manager: XTDeviceManagerInterface | None = None
        self.hass = hass
        if iot_manager := device_manager.get_account_by_name(account_name=MESSAGE_SOURCE_TUYA_IOT):
            self.iot_manager = iot_manager
        if self.iot_manager is None:
            self._supports_native_sync_webrtc = False
            self._supports_native_async_webrtc = False
    
    @staticmethod
    def should_entity_be_added(hass: HomeAssistant, device: XTDevice, multi_manager: MultiManager) -> bool:
        camera_status: list[XTDPCode] = [XTDPCode.RECORD_MODE, XTDPCode.IPC_WORK_MODE, XTDPCode.PHOTO_AGAIN]
        for test_status in camera_status:
            if test_status in device.status:
                return True
        if device.category in ["videolock"]:
            return True
        return False
    
    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        if self.iot_manager is None:
            return await super().async_handle_async_webrtc_offer(offer_sdp, session_id, send_message)
        LOGGER.warning(f"async_handle_async_webrtc_offer: offer sdp:  {offer_sdp}")
        LOGGER.warning(f"async_handle_async_webrtc_offer: session_id: {session_id}")
        return await self.iot_manager.async_handle_async_webrtc_offer(offer_sdp, session_id, send_message, self.device, self.hass)
    
    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Handle a WebRTC candidate."""
        if self.iot_manager is None:
            return await super().async_on_webrtc_candidate(session_id, candidate)
        LOGGER.warning(f"async_on_webrtc_candidate: candidate:  {candidate}")
        LOGGER.warning(f"async_on_webrtc_candidate: session_id: {session_id}")