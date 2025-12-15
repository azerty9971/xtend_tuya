"""Support for XT cameras."""

from __future__ import annotations
import json
import functools
from typing import Any, cast
from enum import IntEnum
from webrtc_models import (
    RTCIceCandidateInit,
    RTCIceServer,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback, HassJob, HassJobType
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.camera.const import (
    StreamType,
)
from homeassistant.components.camera.webrtc import (
    WebRTCSendMessage,
    WebRTCClientConfiguration,
)
from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
    XTDeviceManagerInterface,
)
from .const import (
    TUYA_DISCOVERY_NEW,
    XTDPCode,
    MESSAGE_SOURCE_TUYA_IOT,
    XTMultiManagerProperties,
    XTMultiManagerPostSetupCallbackPriority,
    LOGGER,  # noqa: F401
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaCameraEntity,
    TuyaDPCodeBooleanWrapper,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)


class WebRTCStreamQuality(IntEnum):
    HIGH_QUALITY = 0
    LOW_QUALITY = 1


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
    this_platform = Platform.CAMERA

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[tuple[str, ...], tuple[str, ...]],
        XTEntityDescriptorManager.get_platform_descriptors(
            CAMERAS, entry.runtime_data.multi_manager, None, this_platform
        ),
    )

    @callback
    async def add_camera_devices(device_map) -> None:
        if hass_data.manager is None:
            return
        entities: list[XTCameraEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if XTCameraEntity.should_entity_be_added(
                    hass, device, hass_data.manager, supported_descriptors
                ):
                    entity = XTCameraEntity(
                        device,
                        hass_data.manager,
                        hass,
                        None,
                        WebRTCStreamQuality.HIGH_QUALITY,
                        motion_detection_switch=TuyaDPCodeBooleanWrapper.find_dpcode(
                            device, XTDPCode.MOTION_SWITCH, prefer_function=True
                        ),
                        recording_status=TuyaDPCodeBooleanWrapper.find_dpcode(
                            device, XTDPCode.RECORD_SWITCH
                        ),
                    )
                    await entity.get_webrtc_config()
                    if entity.webrtc_configuration is None:
                        entity.disable_webrtc()
                    if (
                        entity.supports_webrtc() is False
                        and await entity.stream_source() is None
                    ):
                        # this device doesn't support webrtc or rtsp, skip it...
                        continue
                    entities.append(entity)
                    if entity.has_multiple_streams:
                        entities.append(
                            XTCameraEntity(
                                device,
                                hass_data.manager,
                                hass,
                                entity.webrtc_configuration,
                                WebRTCStreamQuality.LOW_QUALITY,
                                motion_detection_switch=TuyaDPCodeBooleanWrapper.find_dpcode(
                                    device, XTDPCode.MOTION_SWITCH, prefer_function=True
                                ),
                                recording_status=TuyaDPCodeBooleanWrapper.find_dpcode(
                                    device, XTDPCode.RECORD_SWITCH
                                ),
                            )
                        )

        async_add_entities(entities)

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered Tuya camera."""
        if hass_data.manager is None:
            return None
        if restrict_dpcode is not None:
            return None
        hass_data.manager.add_post_setup_callback(
            XTMultiManagerPostSetupCallbackPriority.PRIORITY_LAST,
            add_camera_devices,
            device_map,
        )

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
        webrtc_config: WebRTCClientConfiguration | None = None,
        stream_quality: WebRTCStreamQuality = WebRTCStreamQuality.HIGH_QUALITY,
        *,
        motion_detection_switch: TuyaDPCodeBooleanWrapper | None = None,
        recording_status: TuyaDPCodeBooleanWrapper | None = None,
    ) -> None:
        """Init XT Camera."""
        super(XTCameraEntity, self).__init__(device, device_manager)
        super(XTEntity, self).__init__(
            device,
            device_manager,  # type: ignore
            motion_detection_switch=None,
            recording_status=None,
        )
        if stream_quality != WebRTCStreamQuality.HIGH_QUALITY:
            self._attr_unique_id = f"tuya.{device.id}_{stream_quality}"
        self.device = device
        self.device_manager = device_manager
        self.iot_manager: XTDeviceManagerInterface | None = None
        self._hass = hass
        self.hass = hass
        self.webrtc_configuration: WebRTCClientConfiguration | None = webrtc_config
        self.wait_for_candidates = None
        self.supports_2way_audio: bool = False
        self.has_multiple_streams: bool = False
        self.stream_quality = stream_quality
        if iot_manager := device_manager.get_account_by_name(
            account_name=MESSAGE_SOURCE_TUYA_IOT
        ):
            self.iot_manager = iot_manager
        if self.iot_manager is None:
            self.disable_webrtc()
        device_manager.set_general_property(
            XTMultiManagerProperties.CAMERA_DEVICE_ID, device.id
        )

    @staticmethod
    def should_entity_be_added(
        hass: HomeAssistant,
        device: XTDevice,
        multi_manager: MultiManager,
        merged_categories: tuple[str, ...],
    ) -> bool:
        camera_status: list[XTDPCode] = [
            XTDPCode.RECORD_MODE,
            XTDPCode.IPC_WORK_MODE,
            XTDPCode.PHOTO_AGAIN,
            XTDPCode.MOVEMENT_DETECT_PIC,
        ]
        for test_status in camera_status:
            if test_status in device.status:
                return True
        if device.category in merged_categories:
            return True
        return False

    def disable_webrtc(self):
        LOGGER.warning(
            f"Disabling WebRTC for device {self.device.name} as it is not supported.",
            stack_info=True,
        )
        self._supports_native_sync_webrtc = False
        self._supports_native_async_webrtc = False

    def supports_webrtc(self) -> bool:
        return StreamType.WEB_RTC in self.camera_capabilities.frontend_stream_types

    async def get_webrtc_config(self) -> None:
        if self.iot_manager is None:
            return None
        self.device_manager.device_watcher.report_message(
            self.device.id, "Getting WebRTC Config 1", self.device
        )
        return_tuple = await self.iot_manager.async_get_webrtc_ice_servers(
            self.device, "GO2RTC", self._hass
        )
        if return_tuple is None:
            return None
        ice_servers = return_tuple[0]
        webrtc_config = return_tuple[1]
        self.device_manager.device_watcher.report_message(
            self.device.id,
            f"WebRTC Configuration: {ice_servers}, {webrtc_config}",
            self.device,
        )
        if ice_servers:
            self.webrtc_configuration = WebRTCClientConfiguration()
            ice_servers_dict: list[dict[str, str]] = json.loads(ice_servers)
            ice_list: list[RTCIceServer] = []
            for ice_server in ice_servers_dict:
                if url := ice_server.get("urls"):
                    credential = ice_server.get("credential")
                    username = ice_server.get("username")
                    ice_list.append(
                        RTCIceServer(urls=url, username=username, credential=credential)
                    )
            self.webrtc_configuration.configuration.ice_servers = ice_list
        if webrtc_config:
            if audio_attribute := cast(
                dict | None, webrtc_config.get("audio_attributes")
            ):
                if call_mode := cast(list | None, audio_attribute.get("call_mode")):
                    if 2 in call_mode:
                        # Device supports 2 way audio
                        self.supports_2way_audio = True
            if not webrtc_config.get("supports_webrtc", False):
                # Disable WebRTC in case we don't support it
                self.disable_webrtc()
            if skill_str := webrtc_config.get("skill"):
                skill_dict: dict[str, Any] = json.loads(skill_str)
                video_list: list[dict[str, Any]] = skill_dict.get("videos", [])
                if len(video_list) > 1:
                    self.has_multiple_streams = True

    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        if self.iot_manager is None:
            return await super().async_handle_async_webrtc_offer(
                offer_sdp, session_id, send_message
            )
        if self.wait_for_candidates:
            self.wait_for_candidates()
        self.wait_for_candidates = async_call_later(
            self._hass,
            1,
            HassJob(
                functools.partial(self.send_closing_candidate, session_id, self.device),
                job_type=HassJobType.Callback,
                cancel_on_shutdown=True,
            ),
        )
        if self.has_multiple_streams:
            self.wait_for_candidates = async_call_later(
                self._hass,
                5,
                HassJob(
                    functools.partial(
                        self.send_resolution_update,
                        session_id,
                        self.device,
                        self.stream_quality,
                    ),
                    job_type=HassJobType.Callback,
                    cancel_on_shutdown=True,
                ),
            )
        return await self.iot_manager.async_handle_async_webrtc_offer(
            offer_sdp,
            session_id,
            send_message,
            self.device,
            self._hass,
        )

    @callback
    def close_webrtc_session(self, session_id: str) -> None:
        """Close the session."""
        if self.iot_manager is None:
            return None
        self.iot_manager.on_webrtc_close_session(session_id, self.device)

    def send_closing_candidate(
        self, session_id: str, device: XTDevice, *_: Any
    ) -> None:
        if self.iot_manager is None:
            return None
        self.iot_manager.on_webrtc_candidate(
            session_id, RTCIceCandidateInit(candidate=""), device
        )

    def send_resolution_update(
        self, session_id: str, device: XTDevice, quality: WebRTCStreamQuality, *_: Any
    ) -> None:
        if self.iot_manager is None:
            return None
        self.iot_manager.set_webrtc_resolution(session_id, quality, device)

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Handle a WebRTC candidate."""
        LOGGER.warning(
            f"Received WebRTC candidate for device {self.device.name}: {candidate}"
        )
        if self.iot_manager is None:
            return await super().async_on_webrtc_candidate(session_id, candidate)
        return await self.iot_manager.async_on_webrtc_candidate(
            session_id, candidate, self.device
        )

    @callback
    def _async_get_webrtc_client_configuration(self) -> WebRTCClientConfiguration:
        """Return the WebRTC client configuration adjustable per integration."""
        if self.iot_manager is None or self.webrtc_configuration is None:
            return super()._async_get_webrtc_client_configuration()
        return self.webrtc_configuration

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        try:
            LOGGER.warning(
                f"Getting stream source for device {self.device.name}", stack_info=True
            )
            return await super().stream_source()
        except Exception as e:
            LOGGER.error(
                f"Error getting stream source for device {self.device.id}: {e}",
                stack_info=True,
            )
            return None
