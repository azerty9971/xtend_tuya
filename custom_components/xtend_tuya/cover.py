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
    """Describes XT cover entity."""
    
    # Additional attributes for XT specific functionality
    control_back_mode: str | None = None

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
        """Initialize the cover entity."""
        # Initialize the entity
        super(XTCoverEntity, self).__init__(device, device_manager, description)
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description


    @property
    def current_cover_position(self) -> int | None:
        """Return current cover position."""
        # Get the position from the parent implementation
        position = super().current_cover_position
        
        if position is None:
            return None
            
        # Get control_back_mode directly from device status
        control_back_mode_dpcode = self.entity_description.control_back_mode
        control_back_mode = self.device.status.get(control_back_mode_dpcode, "forward") if control_back_mode_dpcode else "forward"
        
        # Determine if reverse mode
        is_reverse_mode = control_back_mode != "forward"
        
        # Convert position based on mode
        if is_reverse_mode:
            # In reverse mode, positions match (0=closed, 100=open)
            return position
        # In standard mode, positions are inverted (Tuya: 0=open, 100=closed)
        return 100 - position

    async def async_set_cover_position(self, **kwargs) -> None:
        """Set the cover position."""
        position = kwargs.get("position")
        if position is None:
            return

        # Get control_back_mode directly from device status
        control_back_mode_dpcode = self.entity_description.control_back_mode
        control_back_mode = self.device.status.get(control_back_mode_dpcode, "forward") if control_back_mode_dpcode else "forward"
        is_reverse_mode = control_back_mode != "forward"
        
        # Convert from Home Assistant position to Tuya position
        if is_reverse_mode:
            # In reverse mode, positions match (0=closed, 100=open)
            tuya_position = position
        else:
            # In standard mode, positions are inverted (HA: 0=closed, 100=open)
            tuya_position = 100 - position
        
        # Run the blocking command in a separate thread
        import asyncio
        command = {
            "code": self.entity_description.set_position,
            "value": tuya_position,
        }
        await asyncio.get_event_loop().run_in_executor(
            None, 
            lambda: self.device_manager.send_commands(self.device.id, [command])
        )

    async def async_open_cover(self, **kwargs) -> None:
        """Open the cover."""
        # Get control_back_mode directly from device status
        control_back_mode_dpcode = self.entity_description.control_back_mode
        control_back_mode = self.device.status.get(control_back_mode_dpcode, "forward") if control_back_mode_dpcode else "forward"
        is_reverse_mode = control_back_mode != "forward"
        
        # For open, in standard mode we need to send 0 to Tuya
        # In reverse mode, we need to send 100
        tuya_position = 100 if is_reverse_mode else 0
        
        import asyncio
        command = None
        
        # Use specific open instruction if available
        if hasattr(self.entity_description, "open_instruction_value"):
            command = {
                "code": self.entity_description.key,
                "value": self.entity_description.open_instruction_value,
            }
        elif hasattr(self.entity_description, "set_position"):
            command = {
                "code": self.entity_description.set_position,
                "value": tuya_position,
            }
            
        if command:
            LOGGER.debug("Opening cover with command: %s", command)
            await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: self.device_manager.send_commands(self.device.id, [command])
            )
        else:
            # Fall back to parent implementation
            await super().async_open_cover(**kwargs)

    async def async_close_cover(self, **kwargs) -> None:
        """Close the cover."""
        # Get control_back_mode directly from device status
        control_back_mode_dpcode = self.entity_description.control_back_mode
        control_back_mode = self.device.status.get(control_back_mode_dpcode, "forward") if control_back_mode_dpcode else "forward"
        is_reverse_mode = control_back_mode != "forward"
        
        # For close, in standard mode we need to send 100 to Tuya
        # In reverse mode, we need to send 0
        tuya_position = 0 if is_reverse_mode else 100
        
        import asyncio
        command = None
        
        # Use specific close instruction if available
        if hasattr(self.entity_description, "close_instruction_value"):
            command = {
                "code": self.entity_description.key,
                "value": self.entity_description.close_instruction_value,
            }
        elif hasattr(self.entity_description, "set_position"):
            command = {
                "code": self.entity_description.set_position,
                "value": tuya_position,
            }
            
        if command:
            LOGGER.debug("Closing cover with command: %s", command)
            await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: self.device_manager.send_commands(self.device.id, [command])
            )
        else:
            # Fall back to parent implementation
            await super().async_close_cover(**kwargs)

    async def async_stop_cover(self, **kwargs) -> None:
        """Stop the cover."""
        import asyncio
        command = None
        
        # Use specific stop instruction if available
        if hasattr(self.entity_description, "stop_instruction_value"):
            command = {
                "code": self.entity_description.key,
                "value": self.entity_description.stop_instruction_value,
            }
        
        if command:
            await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: self.device_manager.send_commands(self.device.id, [command])
            )
        else:
            # Fall back to parent implementation if our approach doesn't work
            await super().async_stop_cover(**kwargs)

