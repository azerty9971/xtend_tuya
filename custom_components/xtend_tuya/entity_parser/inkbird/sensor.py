"""Inkbird data parser for base64-encoded sensor data."""

from __future__ import annotations
import struct
import base64
from dataclasses import dataclass
from typing import Any
from enum import (
    StrEnum,
)
from tuya_device_handlers.definition.sensor import (
    SensorDefinition,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfTemperature,
    PERCENTAGE,
    EntityCategory,
)
from ...sensor import (
    XTSensorEntity,
    XTSensorEntityDescription,
)
from ...multi_manager.multi_manager import (
    XTDevice,
    MultiManager,
)
from ...ha_tuya_integration.tuya_integration_imports import (
    TuyaCustomerDevice,
    TuyaDPCodeRawWrapper,
    TuyaDPCodeStringWrapper,
    TuyaRawTypeInformation,
    TuyaStringTypeInformation,
)
from .const import INKBIRD_CHANNELS


class DPCodeInkbirdRawWrapper(TuyaDPCodeRawWrapper):
    """DPCode wrapper for Inkbird base64-encoded data."""

    def __init__(self, dpcode: str, type_information: TuyaRawTypeInformation) -> None:
        super().__init__(dpcode, type_information)
        self.temperature_unit: UnitOfTemperature = UnitOfTemperature.CELSIUS
        self.temperature: float | None = None
        self.humidity: float | None = None
        self.battery: int | None = None

    def update_data(self, device: TuyaCustomerDevice) -> None:
        if decoded_data := super().read_device_status(device):
            _temperature, _humidity, _, self.battery = struct.Struct("<hHIb").unpack(
                decoded_data[1:11]
            )
            self.temperature = _temperature / 10.0
            self.humidity = _humidity / 10.0


class DPCodeInkbirdStringWrapper(TuyaDPCodeStringWrapper):
    """DPCode wrapper for Inkbird base64-encoded data."""

    def __init__(
        self, dpcode: str, type_information: TuyaStringTypeInformation
    ) -> None:
        super().__init__(dpcode, type_information)
        self.temperature_unit: UnitOfTemperature = UnitOfTemperature.CELSIUS
        self.temperature: float | None = None
        self.humidity: float | None = None
        self.battery: int | None = None

    def update_data(self, device: TuyaCustomerDevice) -> None:
        if string_data := super().read_device_status(device):
            if decoded_data := base64.b64decode(string_data):
                _temperature, _humidity, _, self.battery = struct.Struct("<hHIb").unpack(
                    decoded_data[1:11]
                )
                self.temperature = _temperature / 10.0
                self.humidity = _humidity / 10.0


class DPCodeInkbirdTemperatureRawWrapper(DPCodeInkbirdRawWrapper):
    def read_device_status(self, device: TuyaCustomerDevice) -> Any | None:
        self.update_data(device)
        return self.temperature


class DPCodeInkbirdTemperatureStringWrapper(DPCodeInkbirdStringWrapper):
    def read_device_status(self, device: TuyaCustomerDevice) -> Any | None:
        self.update_data(device)
        return self.temperature

class DPCodeInkbirdHumidityRawWrapper(DPCodeInkbirdRawWrapper):
    def read_device_status(self, device: TuyaCustomerDevice) -> Any | None:
        self.update_data(device)
        return self.humidity

class DPCodeInkbirdHumidityStringWrapper(DPCodeInkbirdStringWrapper):
    def read_device_status(self, device: TuyaCustomerDevice) -> Any | None:
        self.update_data(device)
        return self.humidity

class DPCodeInkbirdBatteryRawWrapper(DPCodeInkbirdRawWrapper):
    def read_device_status(self, device: TuyaCustomerDevice) -> Any | None:
        self.update_data(device)
        return self.battery

class DPCodeInkbirdBatteryStringWrapper(DPCodeInkbirdStringWrapper):
    def read_device_status(self, device: TuyaCustomerDevice) -> Any | None:
        self.update_data(device)
        return self.battery

class InkbirdSensor:
    INKBIRD_SENSORS: dict[str, tuple[XTSensorEntityDescription, ...]] = {}

    class DataKeys(StrEnum):
        TEMPERATURE = "temperature"
        HUMIDITY = "humidity"
        BATTERY = "battery"

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
                        key=f"{key}_{InkbirdSensor.DataKeys.TEMPERATURE}",
                        dpcode=key,
                        data_key=InkbirdSensor.DataKeys.TEMPERATURE,
                        translation_key=f"{label}_{InkbirdSensor.DataKeys.TEMPERATURE}",
                        device_class=SensorDeviceClass.TEMPERATURE,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                        entity_registry_enabled_default=enabled_by_default,
                        wrapper_class=(DPCodeInkbirdTemperatureRawWrapper, DPCodeInkbirdTemperatureStringWrapper),
                    )
                )
            if humidity:
                inkbird_channel_sensors.append(
                    InkbirdSensorEntityDescription(
                        key=f"{key}_{InkbirdSensor.DataKeys.HUMIDITY}",
                        dpcode=key,
                        data_key=InkbirdSensor.DataKeys.HUMIDITY,
                        translation_key=f"{label}_{InkbirdSensor.DataKeys.HUMIDITY}",
                        device_class=SensorDeviceClass.HUMIDITY,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=PERCENTAGE,
                        entity_registry_enabled_default=enabled_by_default,
                        wrapper_class=(DPCodeInkbirdHumidityRawWrapper,DPCodeInkbirdHumidityStringWrapper),
                    )
                )
            if battery:
                inkbird_channel_sensors.append(
                    InkbirdSensorEntityDescription(
                        key=f"{key}_{InkbirdSensor.DataKeys.BATTERY}",
                        dpcode=key,
                        data_key="InkbirdSensor.DataKeys.BATTERY",
                        translation_key=f"{label}_{InkbirdSensor.DataKeys.BATTERY}",
                        device_class=SensorDeviceClass.BATTERY,
                        state_class=SensorStateClass.MEASUREMENT,
                        native_unit_of_measurement=PERCENTAGE,
                        entity_category=EntityCategory.DIAGNOSTIC,
                        entity_registry_enabled_default=enabled_by_default,
                        wrapper_class=(DPCodeInkbirdBatteryRawWrapper,DPCodeInkbirdBatteryStringWrapper),
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

    # Key for which data to extract (temperature, humidity, battery)
    data_key: str | None = None

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSensorEntityDescription,
        definition: SensorDefinition,
        supported_descriptors: dict[str, tuple[XTSensorEntityDescription, ...]],
    ) -> XTSensorEntity:
        return XTSensorEntity(
            device=device,
            device_manager=device_manager,
            description=description,
            definition=definition,
            supported_descriptors=supported_descriptors,
        )
