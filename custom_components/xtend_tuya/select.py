"""Support for Tuya select."""

from __future__ import annotations

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TuyaConfigEntry
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
            key=DPCode.SPECIAL_FUNCTION,
            translation_key="special_function",
            entity_category=EntityCategory.CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.ALARM_VOLUME,
            translation_key="alarm_volume",
            entity_category=EntityCategory.CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.SOUND_MODE,
            translation_key="sound_mode",
            entity_category=EntityCategory.CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.ALARM_LOCK,
            translation_key="alarm_lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.CLOSED_OPENED,
            translation_key="close_opened",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "msp": (
        SelectEntityDescription(
            key=DPCode.WORK_MODE,
            translation_key="cat_litter_box_work_mode",
            entity_category=EntityCategory.CONFIG,
        ),
        SelectEntityDescription(
            key=DPCode.STATUS,
            translation_key="cat_litter_box_status",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: TuyaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya select dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya select."""
        entities: list[TuyaSelectEntity] = []
        for device_id in device_ids:
            device = hass_data.manager.device_map[device_id]
            if descriptions := SELECTS.get(device.category):
                entities.extend(
                    TuyaSelectEntity(device, hass_data.manager, description)
                    for description in descriptions
                    if description.key in device.status
                )

        async_add_entities(entities)

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
