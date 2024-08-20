"""Support for Tuya (de)humidifiers."""

from __future__ import annotations

from dataclasses import dataclass

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.humidifier import (
    HumidifierEntity,
    HumidifierEntityDescription,
    HumidifierEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

try:
    from custom_components.tuya.humidifier import ( # type: ignore
        HUMIDIFIERS as HUMIDIFIERS_TUYA
    )
except ImportError:
    from homeassistant.components.tuya.humidifier import (
        HUMIDIFIERS as HUMIDIFIERS_TUYA
    )
from .util import (
    append_dictionnaries
)

from .multi_manager.multi_manager import XTConfigEntry
from .base import IntegerTypeData, TuyaEntity
from .const import TUYA_DISCOVERY_NEW, DPCode, DPType


@dataclass(frozen=True)
class TuyaHumidifierEntityDescription(HumidifierEntityDescription):
    """Describe an Tuya (de)humidifier entity."""

    # DPCode, to use. If None, the key will be used as DPCode
    dpcode: DPCode | tuple[DPCode, ...] | None = None

    current_humidity: DPCode | None = None
    humidity: DPCode | None = None


HUMIDIFIERS: dict[str, TuyaHumidifierEntityDescription] = {
}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya (de)humidifier dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    merged_categories = HUMIDIFIERS
    if not entry.runtime_data.multi_manager.reuse_config:
        merged_categories = append_dictionnaries(HUMIDIFIERS, HUMIDIFIERS_TUYA)

    @callback
    def async_discover_device(device_map) -> None:
        """Discover and add a discovered Tuya (de)humidifier."""
        entities: list[TuyaHumidifierEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if description := merged_categories.get(device.category):
                    entities.append(
                        TuyaHumidifierEntity(device, hass_data.manager, description)
                    )
        async_add_entities(entities)

    hass_data.manager.register_device_descriptors("humidifiers", merged_categories)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaHumidifierEntity(TuyaEntity, HumidifierEntity):
    """Tuya (de)humidifier Device."""

    _current_humidity: IntegerTypeData | None = None
    _set_humidity: IntegerTypeData | None = None
    _switch_dpcode: DPCode | None = None
    entity_description: TuyaHumidifierEntityDescription
    _attr_name = None

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: TuyaHumidifierEntityDescription,
    ) -> None:
        """Init Tuya (de)humidifier."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

        # Determine main switch DPCode
        self._switch_dpcode = self.find_dpcode(
            description.dpcode or DPCode(description.key), prefer_function=True
        )

        # Determine humidity parameters
        if int_type := self.find_dpcode(
            description.humidity, dptype=DPType.INTEGER, prefer_function=True
        ):
            self._set_humidity = int_type
            self._attr_min_humidity = int(int_type.min_scaled)
            self._attr_max_humidity = int(int_type.max_scaled)

        # Determine current humidity DPCode
        if int_type := self.find_dpcode(
            description.current_humidity,
            dptype=DPType.INTEGER,
        ):
            self._current_humidity = int_type

        # Determine mode support and provided modes
        if enum_type := self.find_dpcode(
            DPCode.MODE, dptype=DPType.ENUM, prefer_function=True
        ):
            self._attr_supported_features |= HumidifierEntityFeature.MODES
            self._attr_available_modes = enum_type.range

    @property
    def is_on(self) -> bool:
        """Return the device is on or off."""
        if self._switch_dpcode is None:
            return False
        return self.device.status.get(self._switch_dpcode, False)

    @property
    def mode(self) -> str | None:
        """Return the current mode."""
        return self.device.status.get(DPCode.MODE)

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity we try to reach."""
        if self._set_humidity is None:
            return None

        humidity = self.device.status.get(self._set_humidity.dpcode)
        if humidity is None:
            return None

        return round(self._set_humidity.scale_value(humidity))

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        if self._current_humidity is None:
            return None

        if (
            current_humidity := self.device.status.get(self._current_humidity.dpcode)
        ) is None:
            return None

        return round(self._current_humidity.scale_value(current_humidity))

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._send_command([{"code": self._switch_dpcode, "value": True}])

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._send_command([{"code": self._switch_dpcode, "value": False}])

    def set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        if self._set_humidity is None:
            raise RuntimeError(
                "Cannot set humidity, device doesn't provide methods to set it"
            )

        self._send_command(
            [
                {
                    "code": self._set_humidity.dpcode,
                    "value": self._set_humidity.scale_value_back(humidity),
                }
            ]
        )

    def set_mode(self, mode):
        """Set new target preset mode."""
        self._send_command([{"code": DPCode.MODE, "value": mode}])
