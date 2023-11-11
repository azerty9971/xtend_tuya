"""Support for Tuya select."""
from __future__ import annotations

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import TuyaEntity
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DPCode, DPType
from .util import ConfigMapper

# All descriptions can be found here. Mostly the Enum data types in the
# default instructions set of each category end up being a select.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
SELECTS: dict[str, tuple[SelectEntityDescription, ...]] = {
}

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya select dynamically through Tuya discovery."""
    hass_data: HomeAssistantTuyaData = ConfigMapper.get_tuya_data(hass, entry)

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya select."""
        entities: list[TuyaSelectEntity] = []
        for device_id in device_ids:
            device = hass_data.device_manager.device_map[device_id]
            if descriptions := SELECTS.get(device.category):
                for description in descriptions:
                    if description.key in device.status:
                        entities.append(
                            TuyaSelectEntity(
                                device, hass_data.device_manager, description
                            )
                        )

        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaSelectEntity(TuyaEntity, SelectEntity):
    """Tuya Select Entity."""

    def __init__(
        self,
        device: TuyaDevice,
        device_manager: TuyaDeviceManager,
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
