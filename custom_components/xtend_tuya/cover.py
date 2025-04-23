"""Support for XT Cover."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.cover import (
    CoverDeviceClass,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .util import (
    merge_device_descriptors
)

from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .const import TUYA_DISCOVERY_NEW, XTDPCode
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaCoverEntity,
    TuyaCoverEntityDescription,
)
from .entity import (
    XTEntity,
)

@dataclass(frozen=True)
class XTCoverEntityDescription(TuyaCoverEntityDescription):
    pass


COVERS: dict[str, tuple[XTCoverEntityDescription, ...]] = {
    # Curtain
    # Note: Multiple curtains isn't documented
    # https://developer.tuya.com/en/docs/iot/categorycl?id=Kaiuz1hnpo7df
    "cl": (
        #XTCoverEntityDescription(
        #    key=DPCode.CONTROL,
        #    translation_key="curtain",
        #    current_state=DPCode.SITUATION_SET,
        #    current_position=(DPCode.PERCENT_STATE, DPCode.PERCENT_CONTROL),
        #    set_position=DPCode.PERCENT_CONTROL,
        #    device_class=CoverDeviceClass.CURTAIN,
        #),
        XTCoverEntityDescription(
            key=XTDPCode.CONTROL,
            translation_key="curtain",
            current_state=XTDPCode.SITUATION_SET,
            current_position=(XTDPCode.PERCENT_CONTROL, XTDPCode.PERCENT_STATE),
            set_position=XTDPCode.PERCENT_CONTROL,
            device_class=CoverDeviceClass.CURTAIN,
            ##override_tuya=True,
        ),
        XTCoverEntityDescription(
            key=XTDPCode.CONTROL_2,
            translation_key="curtain_2",
            current_position=XTDPCode.PERCENT_STATE_2,
            set_position=XTDPCode.PERCENT_CONTROL_2,
            device_class=CoverDeviceClass.CURTAIN,
        ),
        XTCoverEntityDescription(
            key=XTDPCode.CONTROL_3,
            translation_key="curtain_3",
            current_position=XTDPCode.PERCENT_STATE_3,
            set_position=XTDPCode.PERCENT_CONTROL_3,
            device_class=CoverDeviceClass.CURTAIN,
        ),
        XTCoverEntityDescription(
            key=XTDPCode.MACH_OPERATE,
            translation_key="curtain",
            current_position=XTDPCode.POSITION,
            set_position=XTDPCode.POSITION,
            device_class=CoverDeviceClass.CURTAIN,
            open_instruction_value="FZ",
            close_instruction_value="ZZ",
            stop_instruction_value="STOP",
        ),
        # switch_1 is an undocumented code that behaves identically to control
        # It is used by the Kogan Smart Blinds Driver
        XTCoverEntityDescription(
            key=XTDPCode.SWITCH_1,
            translation_key="blind",
            current_position=XTDPCode.PERCENT_CONTROL,
            set_position=XTDPCode.PERCENT_CONTROL,
            device_class=CoverDeviceClass.BLIND,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya cover dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    merged_descriptors = COVERS
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.COVER):
        merged_descriptors = merge_device_descriptors(merged_descriptors, new_descriptor)

    @callback
    def async_discover_device(device_map) -> None:
        """Discover and add a discovered tuya cover."""
        entities: list[XTCoverEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if descriptions := merged_descriptors.get(device.category):
                    entities.extend(
                        XTCoverEntity(device, hass_data.manager, XTCoverEntityDescription(**description.__dict__))
                        for description in descriptions
                        if (
                            description.key in device.function
                            or description.key in device.status_range
                        )
                    )

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors("covers", merged_descriptors)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTCoverEntity(XTEntity, TuyaCoverEntity):
    """XT Cover Device."""

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTCoverEntityDescription,
    ) -> None:
        super(XTCoverEntity, self).__init__(device, device_manager, description)
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description