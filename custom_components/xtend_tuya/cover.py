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
from .const import (
    LOGGER,  # noqa: F401
)
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
    CROSS_CATEGORY_DEVICE_DESCRIPTOR,  # noqa: F401
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaCoverEntity,
    TuyaCoverEntityDescription,
    TuyaDPCode,
    TuyaDPType,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)


@dataclass(frozen=True)
class XTCoverEntityDescription(TuyaCoverEntityDescription):
    """Describes XT cover entity."""

    current_state: TuyaDPCode | XTDPCode | None = None  # type: ignore
    current_position: TuyaDPCode | tuple[TuyaDPCode, ...] | XTDPCode | tuple[XTDPCode, ...] | None = None  # type: ignore
    set_position: TuyaDPCode | XTDPCode | None = None  # type: ignore

    # Additional attributes for XT specific functionality
    control_back_mode: str | None = None

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTCoverEntityDescription,
        hass: HomeAssistant,
    ) -> XTCoverEntity:
        return XTCoverEntity(
            device=device,
            device_manager=device_manager,
            description=description,
            hass=hass,
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

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, tuple[XTCoverEntityDescription, ...]],
            dict[str, tuple[XTCoverEntityDescription, ...]],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            COVERS, entry.runtime_data.multi_manager, Platform.COVER
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
                if category_descriptions := XTEntityDescriptorManager.get_category_descriptors(supported_descriptors, device.category):
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
                            description, device, hass_data.manager, hass
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device, description, True, externally_managed_dpcodes
                        )
                    )
                    entities.extend(
                        XTCoverEntity.get_entity_instance(
                            description, device, hass_data.manager, hass
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device, description, False, externally_managed_dpcodes
                        )
                    )

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors(Platform.COVER, supported_descriptors)
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
    ) -> None:
        """Initialize the cover entity."""

        super(XTCoverEntity, self).__init__(device, device_manager, description)
        super(XTEntity, self).__init__(device, device_manager, description)  # type: ignore
        self.device = device
        self.local_hass = hass
        device_manager.post_setup_callbacks.append(self.add_cover_open_close_option)

    @property
    def is_cover_control_inverted(self) -> bool | None:
        if is_reversed := self.device.status.get(XTDPCode.XT_COVER_INVERT_CONTROL):
            if is_reversed == "no":
                return False
            elif is_reversed == "yes":
                return True
        return None

    @property
    def is_cover_status_inverted(self) -> bool | None:
        if is_reversed := self.device.status.get(XTDPCode.XT_COVER_INVERT_STATUS):
            if is_reversed == "no":
                return False
            elif is_reversed == "yes":
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
                self.device.status[XTDPCode.XT_COVER_INVERT_CONTROL] = "no"
                self.device.status_range[XTDPCode.XT_COVER_INVERT_CONTROL] = (
                    XTDeviceStatusRange(
                        code=XTDPCode.XT_COVER_INVERT_CONTROL,
                        type=TuyaDPType.STRING,
                        values="{}",
                        dp_id=0,
                    )
                )
                send_update = True
            if XTDPCode.XT_COVER_INVERT_STATUS not in self.device.status:
                self.device.status[XTDPCode.XT_COVER_INVERT_STATUS] = "no"
                self.device.status_range[XTDPCode.XT_COVER_INVERT_STATUS] = (
                    XTDeviceStatusRange(
                        code=XTDPCode.XT_COVER_INVERT_STATUS,
                        type=TuyaDPType.STRING,
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
                return round(
                    self._current_position.remap_value_to(
                        current_cover_position, 0, 100, reverse=True
                    )
                )
        return current_cover_position

    @property
    def real_current_cover_position(self) -> int | None:
        """Return cover current position."""
        if self._current_position is None:
            return None

        if (position := self.device.status.get(self._current_position.dpcode)) is None:
            return None

        return round(
            self._current_position.remap_value_to(position, 0, 100, reverse=True)
        )

    @property
    def is_closed(self) -> bool | None:
        """Return true if cover is closed."""
        computed_position = 0
        if self.is_cover_status_inverted:
            computed_position = 100

        if self.entity_description.current_state is not None:
            current_state = self.device.status.get(
                self.entity_description.current_state
            )
            if current_state is not None:
                return (
                    current_state in (True, "fully_close")
                ) is not self.is_cover_status_inverted

        position = self.real_current_cover_position
        if position is not None:
            return position == computed_position

        return None

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        value: bool | str = True
        computed_position = 100
        if self.is_cover_control_inverted:
            computed_position = 0
        if self.find_dpcode(
            self.entity_description.key, dptype=TuyaDPType.ENUM, prefer_function=True
        ):
            value = self.entity_description.open_instruction_value

        commands: list[dict[str, str | int]] = [
            {"code": self.entity_description.key, "value": value}
        ]

        if self._set_position is not None:
            # LOGGER.warning(f"Sending cover open: {self._set_position.remap_value_from(computed_position, 0, 100, reverse=True)}")
            commands.append(
                {
                    "code": self._set_position.dpcode,
                    "value": round(
                        self._set_position.remap_value_from(
                            computed_position, 0, 100, reverse=True
                        ),
                    ),
                }
            )

        self._send_command(commands)

    def close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        value: bool | str = False
        computed_position = 0
        if self.is_cover_control_inverted:
            computed_position = 100
        if self.find_dpcode(
            self.entity_description.key, dptype=TuyaDPType.ENUM, prefer_function=True
        ):
            value = self.entity_description.close_instruction_value

        commands: list[dict[str, str | int]] = [
            {"code": self.entity_description.key, "value": value}
        ]

        if self._set_position is not None:
            # LOGGER.warning(f"Sending cover close: {self._set_position.remap_value_from(computed_position, 0, 100, reverse=True)}")
            commands.append(
                {
                    "code": self._set_position.dpcode,
                    "value": round(
                        self._set_position.remap_value_from(
                            computed_position, 0, 100, reverse=True
                        ),
                    ),
                }
            )

        self._send_command(commands)

    def set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        computed_position = kwargs[ATTR_POSITION]
        if self.is_cover_control_inverted:
            computed_position = 100 - computed_position
        if self._set_position is None:
            raise RuntimeError(
                "Cannot set position, device doesn't provide methods to set it"
            )

        self._send_command(
            [
                {
                    "code": self._set_position.dpcode,
                    "value": round(
                        self._set_position.remap_value_from(
                            computed_position, 0, 100, reverse=True
                        )
                    ),
                }
            ]
        )

    @staticmethod
    def get_entity_instance(
        description: XTCoverEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
        hass: HomeAssistant,
    ) -> XTCoverEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(
                device, device_manager, description, hass
            )
        return XTCoverEntity(
            device,
            device_manager,
            XTCoverEntityDescription(**description.__dict__),
            hass,
        )
