"""Inkbird data parser for base64-encoded sensor data."""

from __future__ import annotations
import base64
import struct
from dataclasses import dataclass
from typing import Self, Any
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfTemperature,
    PERCENTAGE,
    EntityCategory,
)
from ...const import LOGGER
from ...sensor import (
    XTSensorEntity,
    XTSensorEntityDescription,
)
from ...multi_manager.multi_manager import (
    XTDevice,
    MultiManager,
)
from .const import INKBIRD_CHANNELS


class InkbirdSensor:
    INKBIRD_SENSORS: dict[str, tuple[XTSensorEntityDescription, ...]] = {}

    @staticmethod
    def initialize_sensor() -> None:
        inkbird_channel_sensors: list[InkbirdSensorEntityDescription] = []
        for (
            key,
            label,
            temperature,
            humidity,
            battery,
            enabled_by_default,
        ) in INKBIRD_CHANNELS:
            if temperature:
                inkbird_channel_sensors.append(
                    InkbirdSensorEntityDescription(
                        key=key,
                        data_key="temperature",
                        translation_key=f"{label}_temperature",
                        device_class=SensorDeviceClass.TEMPERATURE,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                        entity_registry_enabled_default=enabled_by_default,
                    )
                )
            if humidity:
                inkbird_channel_sensors.append(
                    InkbirdSensorEntityDescription(
                        key=key,
                        data_key="humidity",
                        translation_key=f"{label}_humidity",
                        device_class=SensorDeviceClass.HUMIDITY,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=PERCENTAGE,
                        entity_registry_enabled_default=enabled_by_default,
                    )
                )
            if battery:
                inkbird_channel_sensors.append(
                    InkbirdSensorEntityDescription(
                        key=key,
                        data_key="battery",
                        translation_key=f"{label}_battery",
                        device_class=SensorDeviceClass.BATTERY,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=PERCENTAGE,
                        entity_category=EntityCategory.DIAGNOSTIC,
                        entity_registry_enabled_default=enabled_by_default,
                    )
                )
        INKBIRD_CHANNEL_SENSORS: tuple[InkbirdSensorEntityDescription, ...] = tuple(
            inkbird_channel_sensors
        )
        InkbirdSensor.INKBIRD_SENSORS = {
            "wsdcg": (*INKBIRD_CHANNEL_SENSORS,),
        }

    @staticmethod
    def get_descriptors_to_merge() -> (
        dict[str, tuple[XTSensorEntityDescription, ...]] | None
    ):
        return InkbirdSensor.INKBIRD_SENSORS


@dataclass(frozen=True)
class InkbirdSensorEntityDescription(XTSensorEntityDescription):
    """Describes Inkbird sensor entity with data parsing."""

    data_key: str | None = (
        None  # Key for which data to extract (temperature, humidity, battery)
    )

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSensorEntityDescription,
    ) -> XTSensorEntity:
        return InkbirdSensorEntity(
            device=device, device_manager=device_manager, description=description
        )


@dataclass
class InkbirdB64TypeData:
    """B64Temperature Type Data."""

    temperature_unit: UnitOfTemperature = UnitOfTemperature.CELSIUS
    temperature: float | None = None
    humidity: float | None = None
    battery: int | None = None

    def __post_init__(self) -> None:
        """Convert temperature to target unit."""
        # Pool sensors register humidity as ~6k, replace with None
        if self.humidity and (self.humidity > 100 or self.humidity < 0):
            self.humidity = None

        # Proactively guard against invalid battery values
        if self.battery and (self.battery > 100 or self.battery < 0):
            self.battery = None

    @classmethod
    def from_raw(cls, data: str) -> Self:
        """Parse the raw, base64 encoded data and return a InkbirdB64TypeData object."""
        # LOGGER.info("🐦 InkbirdB64TypeData.from_raw called with data: %s", data)

        temperature_unit: UnitOfTemperature = UnitOfTemperature.CELSIUS
        battery: int | None = None
        temperature: float | None = None
        humidity: float | None = None

        if len(data) > 0:
            try:
                decoded_bytes = base64.b64decode(data)
                # LOGGER.debug("🐦 Decoded bytes: %s (length: %d)", decoded_bytes.hex(), len(decoded_bytes))

                # Parse temperature, humidity, unknown value, battery from bytes 1-10
                # TODO: Identify what the skipped bytes are in the base station data
                _temperature, _humidity, _, battery = struct.Struct("<hHIb").unpack(
                    decoded_bytes[1:11]
                )
                (temperature, humidity) = _temperature / 10.0, _humidity / 10.0
                # LOGGER.info("🐦 Parsed values - temp: %s°, humidity: %s%%, battery: %s%%, unit: %s",
                #           temperature, humidity, battery, temperature_unit)
            except Exception as e:
                LOGGER.error("🐦 InkbirdB64TypeData.from_raw: %s", e)
                raise ValueError(f"Invalid data: {data}") from e
        else:
            LOGGER.warning("🐦 Empty data provided to from_raw")

        result = cls(
            temperature=temperature,
            humidity=humidity,
            temperature_unit=temperature_unit,
            battery=battery,
        )
        # LOGGER.info("🐦 Created InkbirdB64TypeData: %s", result)
        return result


class InkbirdSensorEntity(XTSensorEntity):
    """Inkbird Channel Sensor Entity with base64 data parsing."""

    entity_description: InkbirdSensorEntityDescription
    _parsed_data: InkbirdB64TypeData | None = None
    _last_raw_data: str | None = None  # Track last raw data to detect changes

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSensorEntityDescription,
    ) -> None:
        self.entity_description = description  # type: ignore

        """Initialize Inkbird channel sensor."""
        # LOGGER.info("🐦 Initializing InkbirdChannelSensorEntity for device %s, key %s, data_key %s",
        #           device.id, description.key, self.entity_description.data_key)
        super().__init__(device, device_manager, description)
        # Override unique_id to include data_key for uniqueness
        self._attr_unique_id = (
            f"{self.device.id}_{description.key}_{self.entity_description.data_key}"
        )
        # LOGGER.info("🐦 Created InkbirdChannelSensorEntity with unique_id: %s", self._attr_unique_id)

        # Initialize parsed data
        self._update_parsed_data()
        # LOGGER.info("🐦 Initial data update completed for %s", self._attr_unique_id)

    @property
    def native_value(self) -> Any:
        """Return the native value of the sensor."""
        # LOGGER.debug("🐦 Getting native_value for %s (data_key: %s)", self.entity_id, self.entity_description.data_key)

        # Check if raw data has changed since last parse
        current_raw_data = self.device.status.get(self.entity_description.key)
        if current_raw_data != self._last_raw_data:
            # LOGGER.debug("🐦 Raw data changed for %s: %s -> %s", self.entity_id, self._last_raw_data, current_raw_data)
            self._update_parsed_data()

        if not self._parsed_data:
            # LOGGER.debug("🐦 No parsed data available for %s", self.entity_id)
            return None

        if self.entity_description.data_key == "temperature":
            value = self._parsed_data.temperature
            # LOGGER.debug("🐦 Temperature value for %s: %s", self.entity_id, value)
            return value
        elif self.entity_description.data_key == "humidity":
            value = self._parsed_data.humidity
            # LOGGER.debug("🐦 Humidity value for %s: %s", self.entity_id, value)
            return value
        elif self.entity_description.data_key == "battery":
            value = self._parsed_data.battery
            # LOGGER.debug("🐦 Battery value for %s: %s", self.entity_id, value)
            return value

        # LOGGER.debug("🐦 Unknown data_key '%s' for %s", self.entity_description.data_key, self.entity_id)
        return None

    @property
    def native_unit_of_measurement(self) -> str | None:  # type: ignore
        """Return the native unit of measurement."""
        if self.entity_description.data_key == "temperature" and self._parsed_data:
            # Use the temperature unit from the parsed data
            if self._parsed_data.temperature_unit:
                return (
                    self._parsed_data.temperature_unit.value
                )  # Convert enum to string
            else:
                return UnitOfTemperature.CELSIUS  # Default to Celsius if None
        return self.entity_description.native_unit_of_measurement

    def _update_parsed_data(self) -> None:
        """Update parsed data from device status."""

        # LOGGER.info("🐦 Updating parsed data for %s (key: %s)", self.entity_id, self.entity_description.key)
        # LOGGER.info("🐦 Device status keys: %s", list(self.device.status.keys()) if self.device.status else "None")

        if raw_data := self.device.status.get(self.entity_description.key):
            # Update last raw data tracker
            self._last_raw_data = raw_data
            # LOGGER.info("🐦 Found raw data for %s: %s", self.entity_id, raw_data)
            try:
                self._parsed_data = InkbirdB64TypeData.from_raw(raw_data)
                # LOGGER.info("🐦 Successfully parsed data for %s: temp=%s, hum=%s, bat=%s",
                #           self.entity_id,
                #           self._parsed_data.temperature,
                #           self._parsed_data.humidity,
                #           self._parsed_data.battery)
            except (ValueError, TypeError) as e:
                LOGGER.warning(
                    "🐦 Failed to parse Inkbird data for %s: %s", self.entity_id, e
                )
                self._parsed_data = None
        else:
            # LOGGER.info("🐦 No raw data found for key '%s' in device status for %s",
            #            self.entity_description.key, self.entity_id)
            self._last_raw_data = None
            self._parsed_data = None
