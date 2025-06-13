"""Inkbird data parser for base64-encoded sensor data."""

from __future__ import annotations

import base64
import struct
from dataclasses import dataclass
from typing import Self

from homeassistant.const import UnitOfTemperature

from .const import LOGGER


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
        LOGGER.info("🐦 InkbirdB64TypeData.from_raw called with data: %s", data)
        
        temperature_unit: UnitOfTemperature = UnitOfTemperature.CELSIUS
        battery: int | None = None
        temperature: float | None = None
        humidity: float | None = None

        if len(data) > 0:
            try:
                decoded_bytes = base64.b64decode(data)
                LOGGER.debug("🐦 Decoded bytes: %s (length: %d)", decoded_bytes.hex(), len(decoded_bytes))
                
                # Parse temperature, humidity, unknown value, battery from bytes 1-10
                # TODO: Identify what the skipped bytes are in the base station data
                _temperature, _humidity, _, battery = struct.Struct("<hHIb").unpack(
                    decoded_bytes[1:11]
                )
                (temperature, humidity) = _temperature / 10.0, _humidity / 10.0
                LOGGER.info("🐦 Parsed values - temp: %s°, humidity: %s%%, battery: %s%%, unit: %s", 
                           temperature, humidity, battery, temperature_unit)
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
        LOGGER.info("🐦 Created InkbirdB64TypeData: %s", result)
        return result
