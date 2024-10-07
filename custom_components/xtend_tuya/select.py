"""Support for Tuya select."""

from __future__ import annotations

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .util import (
    merge_device_descriptors
)

from .multi_manager.multi_manager import XTConfigEntry
from .base import TuyaEntity
from .const import TUYA_DISCOVERY_NEW, DPCode, DPType

# All descriptions can be found here. Mostly the Enum data types in the
# default instructions set of each category end up being a select.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
SELECTS: dict[str, tuple[SelectEntityDescription, ...]] = {
    "jtmspro": (
        SelectEntityDescription(
            key=DPCode.BEEP_VOLUME,
            translation_key="beep_volume",
            entity_category=EntityCategory.CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.ALARM_VOLUME,
            translation_key="alarm_volume",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False
        ),
        SelectEntityDescription(
            key=DPCode.SOUND_MODE,
            translation_key="sound_mode",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False
        ),
    ),
    "mk": (
        SelectEntityDescription(
            key=DPCode.DOORBELL_VOLUME,
            translation_key="doorbell_volume",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "msp": (
        SelectEntityDescription(
            key=DPCode.CLEAN,
            translation_key="cat_litter_box_clean",
            entity_category=EntityCategory.CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.EMPTY,
            translation_key="cat_litter_box_empty",
            entity_category=EntityCategory.CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.STATUS,
            translation_key="cat_litter_box_status",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        SelectEntityDescription(
            key=DPCode.WORK_MODE,
            translation_key="cat_litter_box_work_mode",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "ms_category": (
        SelectEntityDescription(
            key=DPCode.KEY_TONE,
            translation_key="key_tone",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "mzj": (
        SelectEntityDescription(
            key=DPCode.TEMPCHANGER,
            translation_key="change_temp_unit",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "qccdz": (
        SelectEntityDescription(
            key=DPCode.WORK_MODE,
            translation_key="qccdz_work_mode",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya select dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    merged_descriptors = SELECTS
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.SELECT):
        merged_descriptors = merge_device_descriptors(merged_descriptors, new_descriptor)

    @callback
    def async_discover_device(device_map) -> None:
        """Discover and add a discovered Tuya select."""
        entities: list[TuyaSelectEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if descriptions := merged_descriptors.get(device.category):
                    entities.extend(
                        TuyaSelectEntity(device, hass_data.manager, description)
                        for description in descriptions
                        if description.key in device.status
                    )

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors("selects", merged_descriptors)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaSelectEntity(TuyaEntity, SelectEntity):
    """Tuya Select Entity."""

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: SelectEntityDescription,
    ) -> None:
        """Init Tuya sensor."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

        self._attr_options: list[str] = []
        if enum_type := self.find_dpcode(
            description.key, dptype=DPType.ENUM, prefer_function=True
        ):
            self._attr_options = enum_type.range

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        # Raw value
        value = self.device.status.get(self.entity_description.key)
        if value is None or value not in self._attr_options:
            return None

        return value

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        self._send_command(
            [
                {
                    "code": self.entity_description.key,
                    "value": option,
                }
            ]
        )
