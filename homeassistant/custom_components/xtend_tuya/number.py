"""Support for Tuya number."""
from __future__ import annotations

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import IntegerTypeData, TuyaEntity
from .const import DEVICE_CLASS_UNITS, DOMAIN, DOMAIN_ORIG, TUYA_DISCOVERY_NEW, DPCode, DPType
from .util import ConfigMapper

# All descriptions can be found here. Mostly the Integer data types in the
# default instructions set of each category end up being a number.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
NUMBERS: dict[str, tuple[NumberEntityDescription, ...]] = {
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya number dynamically through Tuya discovery."""
    hass_data: HomeAssistantTuyaData = ConfigMapper.get_tuya_data(hass, entry)

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya number."""
        entities: list[TuyaNumberEntity] = []
        for device_id in device_ids:
            device = hass_data.device_manager.device_map[device_id]
            if descriptions := NUMBERS.get(device.category):
                for description in descriptions:
                    if description.key in device.status:
                        entities.append(
                            TuyaNumberEntity(
                                device, hass_data.device_manager, description
                            )
                        )

        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaNumberEntity(TuyaEntity, NumberEntity):
    """Tuya Number Entity."""

    _number: IntegerTypeData | None = None

    def __init__(
        self,
        device: TuyaDevice,
        device_manager: TuyaDeviceManager,
        description: NumberEntityDescription,
    ) -> None:
        """Init Tuya sensor."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

        if int_type := self.find_dpcode(
            description.key, dptype=DPType.INTEGER, prefer_function=True
        ):
            self._number = int_type
            self._attr_native_max_value = self._number.max_scaled
            self._attr_native_min_value = self._number.min_scaled
            self._attr_native_step = self._number.step_scaled

        # Logic to ensure the set device class and API received Unit Of Measurement
        # match Home Assistants requirements.
        if (
            self.device_class is not None
            and not self.device_class.startswith(DOMAIN_ORIG)
            and description.native_unit_of_measurement is None
        ):
            # We cannot have a device class, if the UOM isn't set or the
            # device class cannot be found in the validation mapping.
            if (
                self.native_unit_of_measurement is None
                or self.device_class not in DEVICE_CLASS_UNITS
            ):
                self._attr_device_class = None
                return

            uoms = DEVICE_CLASS_UNITS[self.device_class]
            self._uom = uoms.get(self.native_unit_of_measurement) or uoms.get(
                self.native_unit_of_measurement.lower()
            )

            # Unknown unit of measurement, device class should not be used.
            if self._uom is None:
                self._attr_device_class = None
                return

            # If we still have a device class, we should not use an icon
            if self.device_class:
                self._attr_icon = None

            # Found unit of measurement, use the standardized Unit
            # Use the target conversion unit (if set)
            self._attr_native_unit_of_measurement = (
                self._uom.conversion_unit or self._uom.unit
            )

    @property
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        # Unknown or unsupported data type
        if self._number is None:
            return None

        # Raw value
        if (value := self.device.status.get(self.entity_description.key)) is None:
            return None

        return self._number.scale_value(value)

    def set_native_value(self, value: float) -> None:
        """Set new value."""
        if self._number is None:
            raise RuntimeError("Cannot set value, device doesn't provide type data")

        self._send_command(
            [
                {
                    "code": self.entity_description.key,
                    "value": self._number.scale_value_back(value),
                }
            ]
        )
