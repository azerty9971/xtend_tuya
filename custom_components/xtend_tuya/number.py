"""Support for Tuya number."""

from __future__ import annotations

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TuyaConfigEntry
from .base import IntegerTypeData, TuyaEntity
from .const import DEVICE_CLASS_UNITS, DOMAIN, TUYA_DISCOVERY_NEW, DPCode, DPType

# All descriptions can be found here. Mostly the Integer data types in the
# default instructions set of each category end up being a number.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
NUMBERS: dict[str, tuple[NumberEntityDescription, ...]] = {
    "jtmspro": (
        NumberEntityDescription(
            key=DPCode.AUTO_LOCK_TIME,
            translation_key="auto_lock_time",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "msp": (
        NumberEntityDescription(
            key=DPCode.DELAY_CLEAN_TIME,
            translation_key="delay_clean_time",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.QUIET_TIME_END,
            translation_key="quiet_time_end",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.QUIET_TIME_START,
            translation_key="quiet_time_start",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.SLEEP_START_TIME,
            translation_key="sleep_start_time",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.SLEEP_END_TIME,
            translation_key="sleep_end_time",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.UV_START_TIME,
            translation_key="uv_start_time",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.UV_END_TIME,
            translation_key="uv_end_time",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.DEO_START_TIME,
            translation_key="deo_start_time",
            entity_category=EntityCategory.CONFIG,
        ),
        NumberEntityDescription(
            key=DPCode.DEO_END_TIME,
            translation_key="deo_end_time",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: TuyaConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya number dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    @callback
    def async_discover_device(manager, device_map) -> None:
        """Discover and add a discovered Tuya number."""
        entities: list[TuyaNumberEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            device = device_map[device_id]
            if descriptions := NUMBERS.get(device.category):
                entities.extend(
                    TuyaNumberEntity(device, manager, description)
                    for description in descriptions
                    if description.key in device.status
                )

        async_add_entities(entities)

    async_discover_device(hass_data.manager, hass_data.manager.device_map)
    #async_discover_device(hass_data.manager, hass_data.manager.open_api_device_map)

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaNumberEntity(TuyaEntity, NumberEntity):
    """Tuya Number Entity."""

    _number: IntegerTypeData | None = None

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
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
            and not self.device_class.startswith(DOMAIN)
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
