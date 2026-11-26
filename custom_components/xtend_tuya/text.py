"""Support for Tuya text entities (e.g. thermostat week programs)."""

from __future__ import annotations
from typing import Any, cast
from collections.abc import Callable
from dataclasses import dataclass
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.text import (
    TextEntity,
    TextEntityDescription,
)
from homeassistant.const import EntityCategory, Platform
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .const import (
    TUYA_DISCOVERY_NEW,
    DOMAIN_ORIG,
    XTDPCode,
    CROSS_CATEGORY_DEVICE_DESCRIPTOR,
)
from .util import (
    restrict_descriptor_category,
)
from .multi_manager.multi_manager import (
    MultiManager,
    XTConfigEntry,
    XTDevice,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)
from . import week_program_codec


@dataclass(frozen=True)
class XTTextEntityDescription(TextEntityDescription):
    """Describes a Tuya text entity."""

    # duplicate the entity if handled by another integration
    ignore_other_dp_code_handler: bool = False

    # DP value -> displayed text
    value_to_text: Callable[[XTDevice, str, Any], str | None] | None = None

    # entered text -> DP value (raise ServiceValidationError on bad input)
    text_to_value: Callable[[XTDevice, str, str], Any] | None = None

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTTextEntityDescription,
    ) -> XTTextEntity:
        return XTTextEntity(
            device=device,
            device_manager=device_manager,
            description=XTTextEntityDescription(**description.__dict__),
        )


def _week_program_to_text(device: XTDevice, dpcode: str, value: Any) -> str | None:
    return week_program_codec.to_text(value)


def _text_to_week_program(device: XTDevice, dpcode: str, text: str) -> str:
    day = week_program_codec.day_from_dpcode(dpcode)
    period_count = week_program_codec.DEFAULT_PERIOD_COUNT
    if decoded := week_program_codec.decode(device.status.get(dpcode)):
        # Keep the day byte and period count the device currently uses
        day, periods = decoded
        period_count = len(periods)
    try:
        return week_program_codec.from_text(text, day or 0, period_count)
    except week_program_codec.WeekProgramError as err:
        raise ServiceValidationError(str(err)) from err


def _week_program_description(
    dpcode: XTDPCode, translation_key: str
) -> XTTextEntityDescription:
    return XTTextEntityDescription(
        key=dpcode,
        translation_key=translation_key,
        icon="mdi:calendar-clock",
        entity_category=EntityCategory.CONFIG,
        pattern=week_program_codec.TEXT_PATTERN,
        native_max=255,
        value_to_text=_week_program_to_text,
        text_to_value=_text_to_week_program,
    )


WEEK_PROGRAM_TEXTS: tuple[XTTextEntityDescription, ...] = (
    _week_program_description(XTDPCode.WEEK_PROGRAM_13_1, "week_program_monday"),
    _week_program_description(XTDPCode.WEEK_PROGRAM_13_2, "week_program_tuesday"),
    _week_program_description(XTDPCode.WEEK_PROGRAM_13_3, "week_program_wednesday"),
    _week_program_description(XTDPCode.WEEK_PROGRAM_13_4, "week_program_thursday"),
    _week_program_description(XTDPCode.WEEK_PROGRAM_13_5, "week_program_friday"),
    _week_program_description(XTDPCode.WEEK_PROGRAM_13_6, "week_program_saturday"),
    _week_program_description(XTDPCode.WEEK_PROGRAM_13_7, "week_program_sunday"),
)

TEXTS: dict[str, tuple[XTTextEntityDescription, ...]] = {
    CROSS_CATEGORY_DEVICE_DESCRIPTOR: (),
    # Thermostat
    "wk": (*WEEK_PROGRAM_TEXTS,),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya text entities dynamically through Tuya discovery."""
    hass_data = entry.runtime_data
    this_platform = Platform.TEXT

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, tuple[XTTextEntityDescription, ...]],
            dict[str, tuple[XTTextEntityDescription, ...]],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            TEXTS,
            entry.runtime_data.multi_manager,
            XTTextEntityDescription,
            this_platform,
        ),
    )

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered Tuya text entity."""
        if hass_data.manager is None:
            return
        entities: list[XTTextEntity] = []
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
                            tuple[XTTextEntityDescription, ...],
                            restrict_descriptor_category(
                                category_descriptions, [restrict_dpcode]
                            ),
                        )
                    entities.extend(
                        XTTextEntity.get_entity_instance(
                            description, device, hass_data.manager
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
                        XTTextEntity.get_entity_instance(
                            description, device, hass_data.manager
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


class XTTextEntity(XTEntity, TextEntity):  # type: ignore
    """XT Text entity backed by a single DP."""

    entity_description: XTTextEntityDescription

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTTextEntityDescription,
    ) -> None:
        """Init XT text."""
        super().__init__(
            device=device,
            device_manager=device_manager,
            description=description,
        )
        # Set explicitly so we don't depend on the TuyaEntity constructor
        # signature of the installed Home Assistant version.
        self._attr_unique_id = f"tuya.{device.id}{description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN_ORIG, device.id)})
        self._attr_native_max = description.native_max
        self._attr_pattern = description.pattern
        self.entity_description = description
        self.device = device
        self.device_manager = device_manager
        self._dpcode = XTEntity._get_description_dpcode(description)

    @property
    def native_value(self) -> str | None:  # type: ignore
        """Return the current DP value as text."""
        value = self.device.status.get(self._dpcode)
        if self.entity_description.value_to_text is not None:
            return self.entity_description.value_to_text(
                self.device, self._dpcode, value
            )
        return None if value is None else str(value)

    async def async_set_value(self, value: str) -> None:
        """Send the new value to the device."""
        if self.entity_description.text_to_value is not None:
            dp_value = self.entity_description.text_to_value(
                self.device, self._dpcode, value
            )
        else:
            dp_value = value
        commands = [{"code": self._dpcode, "value": dp_value}]
        try:
            await self.hass.async_add_executor_job(
                self.device_manager.send_commands, self.device.id, commands
            )
        except Exception as err:
            raise HomeAssistantError(
                f"Failed to send {self._dpcode} to {self.device.name}: {err}"
            ) from err
        # Optimistic update, the device confirms through MQTT afterwards
        self.device.status[self._dpcode] = dp_value
        self.async_write_ha_state()

    @staticmethod
    def get_entity_instance(
        description: XTTextEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
    ) -> XTTextEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(device, device_manager, description)
        return XTTextEntity(
            device, device_manager, XTTextEntityDescription(**description.__dict__)
        )
