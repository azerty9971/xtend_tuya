"""Support for XT Cover."""

from __future__ import annotations
from typing import cast
from dataclasses import dataclass
from typing import Any
from homeassistant.components.cover import (
    CoverDeviceClass,
    ATTR_POSITION,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .util import (
    restrict_descriptor_category,
)
from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .multi_manager.shared.shared_classes import (
    XTDeviceStatusRange,
)
from .const import (
    TUYA_DISCOVERY_NEW,
    XTDPCode,
    XTMultiManagerPostSetupCallbackPriority,
    LOGGER,  # noqa: F401
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaCoverEntity,
    TuyaCoverEntityDescription,
    TuyaDPCode,
    TuyaDPType,
    TuyaCoverDPCodePercentageMappingWrapper,
    TuyaCoverIsClosedEnumWrapper,
    TuyaCoverIsClosedInvertedWrapper,
    tuya_cover_get_instruction_wrapper,
    TuyaDeviceWrapper,
    TuyaRemapHelper,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)

class XTCoverDPCodePercentageMappingWrapper(TuyaCoverDPCodePercentageMappingWrapper):
    """XT Cover DPCode percentage mapping wrapper."""

    def get_remap_helper(self) -> TuyaRemapHelper:
        return self._remap_helper

@dataclass(frozen=True)
class XTCoverEntityDescription(TuyaCoverEntityDescription):
    """Describes XT cover entity."""

    current_state: TuyaDPCode | XTDPCode | None = None  # type: ignore
    current_position: (  # type: ignore
        TuyaDPCode | tuple[TuyaDPCode, ...] | XTDPCode | tuple[XTDPCode, ...] | None
    ) = None
    set_position: TuyaDPCode | XTDPCode | None = None  # type: ignore

    # duplicate the entity if handled by another integration
    ignore_other_dp_code_handler: bool = False

    # Additional attributes for XT specific functionality
    control_back_mode: str | None = None

    position_wrapper: type[XTCoverDPCodePercentageMappingWrapper] = XTCoverDPCodePercentageMappingWrapper

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTCoverEntityDescription,
        hass: HomeAssistant,
        *,
        current_position: XTCoverDPCodePercentageMappingWrapper | None,
        current_state_wrapper: TuyaCoverIsClosedInvertedWrapper | TuyaCoverIsClosedEnumWrapper | None,
        instruction_wrapper: TuyaDeviceWrapper | None,
        set_position: XTCoverDPCodePercentageMappingWrapper | None,
        tilt_position: TuyaCoverDPCodePercentageMappingWrapper | None,
    ) -> XTCoverEntity:
        return XTCoverEntity(
            device=device,
            device_manager=device_manager,
            description=XTCoverEntityDescription(**description.__dict__),
            hass=hass,
            current_position=current_position,
            current_state_wrapper=current_state_wrapper,
            instruction_wrapper=instruction_wrapper,
            set_position=set_position,
            tilt_position=tilt_position,
        )


COVERS: dict[str, tuple[XTCoverEntityDescription, ...]] = {
    # Curtain
    # Note: Multiple curtains isn't documented
    # https://developer.tuya.com/en/docs/iot/categorycl?id=Kaiuz1hnpo7df
    "cl": (
        # XTCoverEntityDescription(
        #    key=DPCode.CONTROL,
        #    translation_key="curtain",
        #    current_state=DPCode.SITUATION_SET,
        #    current_position=(DPCode.PERCENT_STATE, DPCode.PERCENT_CONTROL),
        #    set_position=DPCode.PERCENT_CONTROL,
        #    device_class=CoverDeviceClass.CURTAIN,
        # ),
        XTCoverEntityDescription(
            key=XTDPCode.CONTROL,
            translation_key="curtain",
            current_state=XTDPCode.SITUATION_SET,
            current_position=(XTDPCode.PERCENT_CONTROL, XTDPCode.PERCENT_STATE),
            set_position=XTDPCode.PERCENT_CONTROL,
            device_class=CoverDeviceClass.CURTAIN,
            control_back_mode=XTDPCode.CONTROL_BACK_MODE,
        ),
        XTCoverEntityDescription(
            key=XTDPCode.CONTROL_2,
            translation_key="curtain_2",
            current_position=(XTDPCode.PERCENT_CONTROL_2, XTDPCode.PERCENT_STATE_2),
            set_position=XTDPCode.PERCENT_CONTROL_2,
            device_class=CoverDeviceClass.CURTAIN,
            control_back_mode=XTDPCode.CONTROL_BACK_MODE,
        ),
        XTCoverEntityDescription(
            key=XTDPCode.CONTROL_3,
            translation_key="curtain_3",
            current_position=(XTDPCode.PERCENT_CONTROL_3, XTDPCode.PERCENT_STATE_3),
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

COVERS["clkg"] = COVERS["cl"]


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya cover dynamically through Tuya discovery."""
    hass_data = entry.runtime_data
    this_platform = Platform.COVER

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, tuple[XTCoverEntityDescription, ...]],
            dict[str, tuple[XTCoverEntityDescription, ...]],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            COVERS,
            entry.runtime_data.multi_manager,
            XTCoverEntityDescription,
            this_platform,
        ),
    )

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered tuya cover."""
        if hass_data.manager is None:
            return
        entities: list[XTCoverEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if (
                    category_descriptions
                    := XTEntityDescriptorManager.get_category_descriptors(
                        supported_descriptors, device.category
                    )
                ):
                    externally_managed_dpcodes = (
                        XTEntityDescriptorManager.get_category_keys(
                            externally_managed_descriptors.get(device.category)
                        )
                    )
                    if restrict_dpcode is not None:
                        category_descriptions = cast(
                            tuple[XTCoverEntityDescription, ...],
                            restrict_descriptor_category(
                                category_descriptions, [restrict_dpcode]
                            ),
                        )
                    entities.extend(
                        XTCoverEntity.get_entity_instance(
                            description,
                            device,
                            hass_data.manager,
                            hass,
                            current_position=description.position_wrapper.find_dpcode(
                                device,
                                description.current_position,  # type: ignore
                            ),
                            instruction_wrapper=tuya_cover_get_instruction_wrapper(
                                device, description
                            ),
                            current_state_wrapper=description.current_state_wrapper.find_dpcode(
                                device, description.current_state
                            ),
                            set_position=description.position_wrapper.find_dpcode(
                                device, description.set_position, prefer_function=True
                            ),
                            tilt_position=description.position_wrapper.find_dpcode(
                                device,
                                (
                                    TuyaDPCode.ANGLE_HORIZONTAL,
                                    TuyaDPCode.ANGLE_VERTICAL,
                                ),
                                prefer_function=True,
                            ),
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device,
                            this_platform,
                            description,
                            True,
                            externally_managed_dpcodes,
                        )
                    )
                    entities.extend(
                        XTCoverEntity.get_entity_instance(
                            description,
                            device,
                            hass_data.manager,
                            hass,
                            current_position=description.position_wrapper.find_dpcode(
                                device,
                                description.current_position,
                            ),
                            instruction_wrapper=tuya_cover_get_instruction_wrapper(
                                device, description
                            ),
                            current_state_wrapper=description.current_state_wrapper.find_dpcode(
                                device, description.current_state
                            ),
                            set_position=description.position_wrapper.find_dpcode(
                                device, description.set_position, prefer_function=True
                            ),
                            tilt_position=description.position_wrapper.find_dpcode(
                                device,
                                (
                                    TuyaDPCode.ANGLE_HORIZONTAL,
                                    TuyaDPCode.ANGLE_VERTICAL,
                                ),
                                prefer_function=True,
                            ),
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device,
                            this_platform,
                            description,
                            False,
                            externally_managed_dpcodes,
                        )
                    )

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors(this_platform, supported_descriptors)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTCoverEntity(XTEntity, TuyaCoverEntity):
    """XT Cover Device."""

    entity_description: XTCoverEntityDescription  # type: ignore

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTCoverEntityDescription,
        hass: HomeAssistant,
        *,
        current_position: XTCoverDPCodePercentageMappingWrapper | None,
        current_state_wrapper: TuyaCoverIsClosedInvertedWrapper | TuyaCoverIsClosedEnumWrapper | None,
        instruction_wrapper: TuyaDeviceWrapper | None,
        set_position: XTCoverDPCodePercentageMappingWrapper | None,
        tilt_position: TuyaCoverDPCodePercentageMappingWrapper | None,
    ) -> None:
        """Initialize the cover entity."""
        device_manager.device_watcher.report_message(device.id, f"Initializing cover entity {device.name}: current_position: {current_position.dpcode if current_position else None}, set_position: {set_position.dpcode if set_position else None}", device)
        super(XTCoverEntity, self).__init__(device, device_manager, description)
        super(XTEntity, self).__init__(
            device,
            device_manager,  # type: ignore
            description,
            current_position=current_position,
            current_state_wrapper=current_state_wrapper,
            instruction_wrapper=instruction_wrapper,
            set_position=set_position,
            tilt_position=tilt_position,
        )
        self.device = device
        self.local_hass = hass
        self._current_position = current_position or set_position
        self._set_position = set_position
        device_manager.add_post_setup_callback(
            XTMultiManagerPostSetupCallbackPriority.PRIORITY1,
            self.add_cover_open_close_option,
        )

    @property
    def is_cover_control_inverted(self) -> bool | None:
        if is_reversed := self.device.status.get(XTDPCode.XT_COVER_INVERT_CONTROL):
            if is_reversed is False:
                return False
            elif is_reversed is True:
                return True
        return None

    @property
    def is_cover_status_inverted(self) -> bool | None:
        if is_reversed := self.device.status.get(XTDPCode.XT_COVER_INVERT_STATUS):
            if is_reversed is False:
                return False
            elif is_reversed is True:
                return True
        return None

    def add_cover_open_close_option(self) -> None:
        if (
            self.device.get_preference(
                f"{XTDevice.XTDevicePreference.IS_A_COVER_DEVICE}"
            )
            is None
        ):
            self.device.set_preference(
                f"{XTDevice.XTDevicePreference.IS_A_COVER_DEVICE}", True
            )
            send_update = False
            if XTDPCode.XT_COVER_INVERT_CONTROL not in self.device.status:
                self.device.status[XTDPCode.XT_COVER_INVERT_CONTROL] = False
                self.device.status_range[XTDPCode.XT_COVER_INVERT_CONTROL] = (
                    XTDeviceStatusRange(
                        code=XTDPCode.XT_COVER_INVERT_CONTROL,
                        type=TuyaDPType.BOOLEAN,
                        values="{}",
                        dp_id=0,
                    )
                )
                send_update = True
            if XTDPCode.XT_COVER_INVERT_STATUS not in self.device.status:
                self.device.status[XTDPCode.XT_COVER_INVERT_STATUS] = False
                self.device.status_range[XTDPCode.XT_COVER_INVERT_STATUS] = (
                    XTDeviceStatusRange(
                        code=XTDPCode.XT_COVER_INVERT_STATUS,
                        type=TuyaDPType.BOOLEAN,
                        values="{}",
                        dp_id=0,
                    )
                )
                send_update = True
            if send_update:
                dispatcher_send(
                    self.local_hass,
                    TUYA_DISCOVERY_NEW,
                    [self.device.id],
                    XTDPCode.XT_COVER_INVERT_CONTROL,
                )
                dispatcher_send(
                    self.local_hass,
                    TUYA_DISCOVERY_NEW,
                    [self.device.id],
                    XTDPCode.XT_COVER_INVERT_STATUS,
                )

    @property
    def current_cover_position(self) -> int | None:
        current_cover_position = super().current_cover_position
        if current_cover_position is not None:
            if self.is_cover_status_inverted and self._current_position is not None:
                current_cover_position = round(
                    self._current_position.get_remap_helper().remap_value_to(
                        current_cover_position, reverse=True
                    )
                )
        return current_cover_position

    async def _async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if self._set_position is not None:
            await self._async_send_commands(
                self._set_position.get_update_commands(self.device, 100)
            )
            return
        
        if (
            self._instruction_wrapper
            and (options := self._instruction_wrapper.options)
            and "open" in options
        ):
            await self._async_send_wrapper_updates(self._instruction_wrapper, "open")
            return

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if self.is_cover_control_inverted:
            await self._async_close_cover(**kwargs)
        else:
            await self._async_open_cover(**kwargs)
    
    async def _async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        if self._set_position is not None:
            await self._async_send_commands(
                self._set_position.get_update_commands(self.device, 0)
            )
            return
        
        if (
            self._instruction_wrapper
            and (options := self._instruction_wrapper.options)
            and "close" in options
        ):
            await self._async_send_wrapper_updates(self._instruction_wrapper, "close")
            return

    #async def async_close_cover(self, **kwargs: Any) -> None:
    #    if self.is_cover_control_inverted:
    #        await self._async_open_cover(**kwargs)
    #    else:
    #        await self._async_close_cover(**kwargs)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        computed_position = kwargs[ATTR_POSITION]
        if self.is_cover_control_inverted:
            computed_position = 100 - computed_position
            kwargs[ATTR_POSITION] = computed_position
        await super().async_set_cover_position(**kwargs)

    @staticmethod
    def get_entity_instance(
        description: XTCoverEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
        hass: HomeAssistant,
        *,
        current_position: XTCoverDPCodePercentageMappingWrapper | None,
        current_state_wrapper: TuyaCoverIsClosedInvertedWrapper | TuyaCoverIsClosedEnumWrapper | None,
        instruction_wrapper: TuyaDeviceWrapper | None,
        set_position: XTCoverDPCodePercentageMappingWrapper | None,
        tilt_position: TuyaCoverDPCodePercentageMappingWrapper | None,
    ) -> XTCoverEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(
                device,
                device_manager,
                description,
                hass,
                current_position=current_position,
                current_state_wrapper=current_state_wrapper,
                instruction_wrapper=instruction_wrapper,
                set_position=set_position,
                tilt_position=tilt_position,
            )
        return XTCoverEntity(
            device,
            device_manager,
            XTCoverEntityDescription(**description.__dict__),
            hass,
            current_position=current_position,
            current_state_wrapper=current_state_wrapper,
            instruction_wrapper=instruction_wrapper,
            set_position=set_position,
            tilt_position=tilt_position,
        )
