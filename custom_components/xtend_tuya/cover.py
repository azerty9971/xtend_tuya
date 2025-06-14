"""Support for XT Cover."""

from __future__ import annotations

from dataclasses import dataclass
import asyncio

from homeassistant.components.cover import (
    CoverDeviceClass,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    LOGGER,
)
from .util import (
    merge_device_descriptors
)

from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .const import TUYA_DISCOVERY_NEW, XTDPCode, CROSS_CATEGORY_DEVICE_DESCRIPTOR
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaCoverEntity,
    TuyaCoverEntityDescription,
    TuyaDPCode,
)
from .entity import (
    XTEntity,
)

@dataclass(frozen=True)
class XTCoverEntityDescription(TuyaCoverEntityDescription):
    """Describes XT cover entity."""
    current_state: TuyaDPCode | XTDPCode | None = None # type: ignore
    current_position: TuyaDPCode | tuple[TuyaDPCode, ...] | XTDPCode | tuple[XTDPCode, ...] | None = None # type: ignore
    set_position: TuyaDPCode | XTDPCode | None = None # type: ignore

    # Additional attributes for XT specific functionality
    control_back_mode: str | None = None

    def get_entity_instance(self, 
                            device: XTDevice, 
                            device_manager: MultiManager, 
                            description: XTCoverEntityDescription
                            ) -> XTCoverEntity:
        return XTCoverEntity(device=device, 
                              device_manager=device_manager, 
                              description=description)

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
            control_back_mode=XTDPCode.CONTROL_BACK_MODE,
            ##override_tuya=True,
        ),
        XTCoverEntityDescription(
            key=XTDPCode.CONTROL_2,
            translation_key="curtain_2",
            current_position=XTDPCode.PERCENT_STATE_2,
            set_position=XTDPCode.PERCENT_CONTROL_2,
            control_back_mode=XTDPCode.CONTROL_BACK_MODE,
            device_class=CoverDeviceClass.CURTAIN,
        ),
        XTCoverEntityDescription(
            key=XTDPCode.CONTROL_3,
            translation_key="curtain_3",
            current_position=XTDPCode.PERCENT_STATE_3,
            set_position=XTDPCode.PERCENT_CONTROL_3,
            device_class=CoverDeviceClass.CURTAIN,
            control_back_mode=XTDPCode.CONTROL_BACK_MODE,
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
            control_back_mode=XTDPCode.CONTROL_BACK_MODE,
     ),
        # switch_1 is an undocumented code that behaves identically to control
        # It is used by the Kogan Smart Blinds Driver
        XTCoverEntityDescription(
            key=XTDPCode.SWITCH_1,
            translation_key="blind",
            current_position=XTDPCode.PERCENT_CONTROL,
            set_position=XTDPCode.PERCENT_CONTROL,
            device_class=CoverDeviceClass.BLIND,
            control_back_mode=XTDPCode.CONTROL_BACK_MODE,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya cover dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    merged_descriptors = COVERS
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.COVER):
        merged_descriptors = merge_device_descriptors(merged_descriptors, new_descriptor)

    @callback
    def async_discover_device(device_map) -> None:
        """Discover and add a discovered tuya cover."""
        if hass_data.manager is None:
            return
        entities: list[XTCoverEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if device.get_preference(f"{XTDevice.XTDevicePreference.REDISCOVER_CROSS_CAT_ENTITIES}", False):
                    if descriptions := merged_descriptors.get(CROSS_CATEGORY_DEVICE_DESCRIPTOR):
                        entities.extend(
                            XTCoverEntity.get_entity_instance(description, device, hass_data.manager)
                            for description in descriptions
                            if (
                                description.key in device.function
                                or description.key in device.status_range
                            )
                        )
                    continue
                if descriptions := merged_descriptors.get(device.category):
                    entities.extend(
                        XTCoverEntity.get_entity_instance(description, device, hass_data.manager)
                        for description in descriptions
                        if (
                            description.key in device.function
                            or description.key in device.status_range
                        )
                    )
                if descriptions := merged_descriptors.get(CROSS_CATEGORY_DEVICE_DESCRIPTOR):
                    entities.extend(
                        XTCoverEntity.get_entity_instance(description, device, hass_data.manager)
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

    entity_description: XTCoverEntityDescription # type: ignore

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTCoverEntityDescription,
    ) -> None:
        """Initialize the cover entity."""
        
        super(XTCoverEntity, self).__init__(device, device_manager, description)
        super(XTEntity, self).__init__(device, device_manager, description) # type: ignore
        self.device = device

    @property
    def is_cover_position_reversed(self) -> bool:
        control_back_mode_dpcode = self.entity_description.control_back_mode
        control_back_mode = self.device.status.get(control_back_mode_dpcode, "forward") if control_back_mode_dpcode else "forward"
        return control_back_mode != "forward"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self.device.get_preference(f"{XTDevice.XTDevicePreference.IS_A_COVER_DEVICE}") is None:
            self.device.set_preference(f"{XTDevice.XTDevicePreference.IS_A_COVER_DEVICE}", True)
            if XTDPCode.COVER_OPEN_CLOSE_IS_INVERTED not in self.device.status:
                self.device.status[XTDPCode.COVER_OPEN_CLOSE_IS_INVERTED] = False
            self.device.set_preference(f"{XTDevice.XTDevicePreference.REDISCOVER_CROSS_CAT_ENTITIES}", True)
            dispatcher_send(self.hass, TUYA_DISCOVERY_NEW, [self.device.id])


    @staticmethod
    def get_entity_instance(description: XTCoverEntityDescription, device: XTDevice, device_manager: MultiManager) -> XTCoverEntity:
        if hasattr(description, "get_entity_instance") and callable(getattr(description, "get_entity_instance")):
            return description.get_entity_instance(device, device_manager, description)
        return XTCoverEntity(device, device_manager, XTCoverEntityDescription(**description.__dict__))