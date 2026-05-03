"""Support for XT Cover."""

from __future__ import annotations
from typing import cast
from dataclasses import dataclass
from typing import Any
from tuya_device_handlers.definition.cover import (
    TuyaCoverDefinition,
)
from tuya_device_handlers.device_wrapper.common import DPCodeTypeInformationWrapper
from tuya_device_handlers.device_wrapper.cover import (
    CoverInstructionBooleanWrapper,
)
from tuya_device_handlers.helpers.homeassistant import TuyaCoverAction
from homeassistant.components.cover import (
    CoverDeviceClass,
    ATTR_POSITION,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .util import (
    restrict_descriptor_category,
)
from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .const import (
    TUYA_DISCOVERY_NEW,
    XTDPCode,  # noqa: F401
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaCoverEntity,
    TuyaCoverEntityDescription,
    TuyaDPCode,
    TuyaRemapHelper,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)

@dataclass
class XTCoverConfigurableProperties:
    invert_status: bool = False
    invert_control: bool = False

@dataclass(frozen=True)
class XTCoverEntityDescription(TuyaCoverEntityDescription):
    """Describes XT cover entity."""

    current_state: TuyaDPCode | XTDPCode | None = None  # type: ignore
    current_position: (  # type: ignore
        TuyaDPCode | tuple[TuyaDPCode, ...] | XTDPCode | tuple[XTDPCode, ...] | None
    ) = None
    set_position: TuyaDPCode | tuple[TuyaDPCode, ...] | XTDPCode | tuple[XTDPCode, ...] | None = None  # type: ignore

    # duplicate the entity if handled by another integration
    ignore_other_dp_code_handler: bool = False

    # Additional attributes for XT specific functionality
    control_back_mode: str | None = None

    # position_wrapper: type[XTCoverDPCodePercentageMappingWrapper] = (
    #     XTCoverDPCodePercentageMappingWrapper
    # )

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTCoverEntityDescription,
        hass: HomeAssistant,
        definition: TuyaCoverDefinition,
    ) -> XTCoverEntity:
        return XTCoverEntity(
            device=device,
            device_manager=device_manager,
            description=XTCoverEntityDescription(**description.__dict__),
            hass=hass,
            definition=definition,
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
            set_position=(XTDPCode.PERCENT_CONTROL, XTDPCode.PERCENT_STATE),
            device_class=CoverDeviceClass.CURTAIN,
            control_back_mode=XTDPCode.CONTROL_BACK_MODE,
        ),
        XTCoverEntityDescription(
            key=XTDPCode.CONTROL_2,
            translation_key="curtain_2",
            current_position=(XTDPCode.PERCENT_CONTROL_2, XTDPCode.PERCENT_STATE_2),
            set_position=(XTDPCode.PERCENT_CONTROL_2, XTDPCode.PERCENT_STATE_2),
            device_class=CoverDeviceClass.CURTAIN,
            control_back_mode=XTDPCode.CONTROL_BACK_MODE,
        ),
        XTCoverEntityDescription(
            key=XTDPCode.CONTROL_3,
            translation_key="curtain_3",
            current_position=(XTDPCode.PERCENT_CONTROL_3, XTDPCode.PERCENT_STATE_3),
            set_position=(XTDPCode.PERCENT_CONTROL_3, XTDPCode.PERCENT_STATE_3),
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


def get_default_definition(
    device: XTDevice,
    *,
    current_position_dpcode: str | tuple[str, ...] | None,
    current_state_dpcode: str | tuple[str, ...] | None,
    instruction_dpcode: str,
    set_position_dpcode: str | tuple[str, ...] | None,
    current_state_wrapper: type[DPCodeTypeInformationWrapper],  # type: ignore[type-arg]
    instruction_wrapper: type[DPCodeTypeInformationWrapper],  # type: ignore[type-arg]
    position_wrapper: type[DPCodeTypeInformationWrapper],  # type: ignore[type-arg]
) -> TuyaCoverDefinition | None:
    if not (
        instruction_dpcode in device.function
        or instruction_dpcode in device.status_range
    ):
        return None

    return TuyaCoverDefinition(
        current_position_wrapper=position_wrapper.find_dpcode(
            device, current_position_dpcode
        ),
        current_state_wrapper=current_state_wrapper.find_dpcode(
            device, current_state_dpcode
        ),
        instruction_wrapper=instruction_wrapper.find_dpcode(
            device, instruction_dpcode, prefer_function=True
        )
        or CoverInstructionBooleanWrapper.find_dpcode(
            device, instruction_dpcode, prefer_function=True
        ),
        set_position_wrapper=position_wrapper.find_dpcode(
            device, set_position_dpcode, prefer_function=True
        ),
        tilt_position_wrapper=position_wrapper.find_dpcode(
            device, ("angle_horizontal", "angle_vertical"), prefer_function=True
        ),
    )


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
                if category_descriptions := XTEntityDescriptorManager.get_category_descriptors(
                    supported_descriptors, device.category
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
                            description=description,
                            device=device,
                            device_manager=hass_data.manager,
                            hass=hass,
                            definition=definition,
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device=device,
                            platform=this_platform,
                            description=description,
                            first_pass=True,
                            externally_managed_dpcodes=externally_managed_dpcodes,
                        )
                        and (
                            definition := get_default_definition(
                                device=device,
                                current_position_dpcode=description.current_position,
                                current_state_dpcode=description.current_state,
                                current_state_wrapper=description.current_state_wrapper,
                                instruction_dpcode=description.key,
                                instruction_wrapper=description.instruction_wrapper,
                                position_wrapper=description.position_wrapper,
                                set_position_dpcode=description.set_position,
                            )
                        )
                    )
                    entities.extend(
                        XTCoverEntity.get_entity_instance(
                            device=device,
                            device_manager=hass_data.manager,
                            description=description,
                            hass=hass,
                            definition=definition,
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device,
                            this_platform,
                            description,
                            False,
                            externally_managed_dpcodes,
                        )
                        and (
                            definition := get_default_definition(
                                device,
                                current_position_dpcode=description.current_position,
                                current_state_dpcode=description.current_state,
                                current_state_wrapper=description.current_state_wrapper,
                                instruction_dpcode=description.key,
                                instruction_wrapper=description.instruction_wrapper,
                                position_wrapper=description.position_wrapper,
                                set_position_dpcode=description.set_position,
                            )
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
        definition: TuyaCoverDefinition,
    ) -> None:
        """Initialize the cover entity."""
        super(XTCoverEntity, self).__init__(
            device=device,
            device_manager=device_manager,  # type: ignore
            description=description,
            definition=definition,
        )
        super(XTEntity, self).__init__(
            device=device,
            device_manager=device_manager,  # type: ignore
            description=description,
            definition=definition,
        )
        self.device = device
        self.local_hass = hass
        self._current_position = definition.current_position_wrapper
        self._remap_helper = cast(
            TuyaRemapHelper | None,
            getattr(
                self._current_position,
                "_remap_helper",
                None,
            ),
        )
        self.device.set_preference(
            f"{XTDevice.XTDevicePreference.COVER_DEVICE_ENTITY}",
            self,
        )
        self.configurable_properties = cast(
            XTCoverConfigurableProperties, self.get_configurable_properties()
        )
    
    def get_configurable_properties_type(self) -> type[Any] | None:
        return XTCoverConfigurableProperties

    def get_configurable_properties_key(self) -> str | None:
        return "cover_configurable_properties"
    
    def refresh_configurable_properties(self):
        self.configurable_properties = cast(
            XTCoverConfigurableProperties, self.get_configurable_properties()
        )

    @property
    def is_cover_control_inverted(self) -> bool:
        return self.configurable_properties.invert_control

    @property
    def is_cover_status_inverted(self) -> bool:
        return self.configurable_properties.invert_status

    @property
    def current_cover_position(self) -> int | None:
        current_cover_position = super().current_cover_position
        if current_cover_position is not None:
            if self.is_cover_status_inverted:
                if self._remap_helper is not None:
                    current_cover_position = round(
                        self._remap_helper.remap_value_to(
                            current_cover_position, reverse=True
                        )
                    )
        return current_cover_position

    @property
    def is_closed(self) -> bool | None:
        return super().is_closed

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
            and TuyaCoverAction.OPEN in options
        ):
            await self._async_send_wrapper_updates(
                self._instruction_wrapper, TuyaCoverAction.OPEN
            )
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
            and TuyaCoverAction.CLOSE in options
        ):
            await self._async_send_wrapper_updates(
                self._instruction_wrapper, TuyaCoverAction.CLOSE
            )
            return

    async def async_close_cover(self, **kwargs: Any) -> None:
        if self.is_cover_control_inverted:
            await self._async_open_cover(**kwargs)
        else:
            await self._async_close_cover(**kwargs)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        computed_position = kwargs[ATTR_POSITION]
        if self.is_cover_control_inverted and self._remap_helper is not None:
            computed_position = round(
                self._remap_helper.remap_value_to(computed_position, reverse=True)
            )
            kwargs[ATTR_POSITION] = computed_position
        await super().async_set_cover_position(**kwargs)

    @staticmethod
    def get_entity_instance(
        device: XTDevice,
        device_manager: MultiManager,
        description: XTCoverEntityDescription,
        hass: HomeAssistant,
        definition: TuyaCoverDefinition,
    ) -> XTCoverEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(
                device=device,
                device_manager=device_manager,
                description=description,
                hass=hass,
                definition=definition,
            )
        return XTCoverEntity(
            device=device,
            device_manager=device_manager,
            description=XTCoverEntityDescription(**description.__dict__),
            hass=hass,
            definition=definition,
        )
