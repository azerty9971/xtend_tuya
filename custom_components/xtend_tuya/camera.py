"""Support for Tuya cameras."""

from __future__ import annotations

from tuya_sharing import CustomerDevice, Manager

from homeassistant.const import Platform
from homeassistant.components import ffmpeg
from homeassistant.components.camera import Camera as CameraEntity, CameraEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .util import (
    append_lists
)

from .multi_manager.multi_manager import XTConfigEntry
from .base import TuyaEntity
from .const import TUYA_DISCOVERY_NEW, DPCode

# All descriptions can be found here:
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
CAMERAS: tuple[str, ...] = (
)


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya cameras dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    merged_categories = CAMERAS
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.CAMERA):
        merged_categories = tuple(append_lists(CAMERAS, new_descriptor))

    @callback
    def async_discover_device(device_map) -> None:
        """Discover and add a discovered Tuya camera."""
        entities: list[TuyaCameraEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if device.category in merged_categories:
                    entities.append(TuyaCameraEntity(device, hass_data.manager))

        async_add_entities(entities)

    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaCameraEntity(TuyaEntity, CameraEntity):
    """Tuya Camera Entity."""

    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_brand = "Tuya"
    _attr_name = None

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
    ) -> None:
        """Init Tuya Camera."""
        super().__init__(device, device_manager)
        CameraEntity.__init__(self)
        self._attr_model = device.product_name

    @property
    def is_recording(self) -> bool:
        """Return true if the device is recording."""
        return self.device.status.get(DPCode.RECORD_SWITCH, False)

    @property
    def motion_detection_enabled(self) -> bool:
        """Return the camera motion detection status."""
        return self.device.status.get(DPCode.MOTION_SWITCH, False)

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        return await self.hass.async_add_executor_job(
            self.device_manager.get_device_stream_allocate,
            self.device.id,
            "rtsp",
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        stream_source = await self.stream_source()
        if not stream_source:
            return None
        return await ffmpeg.async_get_image(
            self.hass,
            stream_source,
            width=width,
            height=height,
        )

    def enable_motion_detection(self) -> None:
        """Enable motion detection in the camera."""
        self._send_command([{"code": DPCode.MOTION_SWITCH, "value": True}])

    def disable_motion_detection(self) -> None:
        """Disable motion detection in camera."""
        self._send_command([{"code": DPCode.MOTION_SWITCH, "value": False}])
