"""Inkbird data parser for base64-encoded sensor data."""

from __future__ import annotations
import struct
from dataclasses import dataclass
from typing import Any
from enum import (
    StrEnum,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.tuya.models import TypeInformation
from homeassistant.const import (
    UnitOfTemperature,
    PERCENTAGE,
    EntityCategory,
)
from ...sensor import (
    XTSensorEntity,
    XTSensorEntityDescription,
    TuyaDPCodeWrapper,
)
from ...multi_manager.multi_manager import (
    XTDevice,
    MultiManager,
)
from ...ha_tuya_integration.tuya_integration_imports import (
    TuyaCustomerDevice,
    TuyaDPCodeBase64Wrapper,
)
from .const import INKBIRD_CHANNELS


class DPCodeInkbirdWrapper(TuyaDPCodeBase64Wrapper):
    """DPCode wrapper for Inkbird base64-encoded data."""

    def __init__(self, dpcode: str, type_information: TypeInformation) -> None:
        super().__init__(dpcode, type_information)
        self.temperature_unit: UnitOfTemperature = UnitOfTemperature.CELSIUS
        self.temperature: float | None = None
        self.humidity: float | None = None
        self.battery: int | None = None

    def update_data(self, device: TuyaCustomerDevice) -> None:
        if decoded_data := self.read_bytes(device):
            _temperature, _humidity, _, self.battery = struct.Struct("<hHIb").unpack(
                decoded_data[1:11]
            )
            self.temperature = _temperature / 10.0
            self.humidity = _humidity / 10.0


class DPCodeInkbirdTemperatureWrapper(DPCodeInkbirdWrapper):

    def read_device_status(self, device: TuyaCustomerDevice) -> Any | None:
        self.update_data(device)
        return self.temperature


class DPCodeInkbirdHumidityWrapper(DPCodeInkbirdWrapper):

    def read_device_status(self, device: TuyaCustomerDevice) -> Any | None:
        self.update_data(device)
        return self.humidity


class DPCodeInkbirdBatteryWrapper(DPCodeInkbirdWrapper):

    def read_device_status(self, device: TuyaCustomerDevice) -> Any | None:
        self.update_data(device)
        return self.battery


class InkbirdSensor:
    INKBIRD_SENSORS: dict[str, tuple[XTSensorEntityDescription, ...]] = {}

    class DataKeys(StrEnum):
        TEMPERATURE = "temperature"
        HUMIDITY    = "humidity"
        BATTERY     = "battery"

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
                        wrapper_class=(DPCodeInkbirdTemperatureWrapper,),
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
                        wrapper_class=(DPCodeInkbirdHumidityWrapper,),
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
                        wrapper_class=(DPCodeInkbirdBatteryWrapper,),
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
        dpcode_wrapper: TuyaDPCodeWrapper,
    ) -> XTSensorEntity:
        return XTSensorEntity(
            device=device,
            device_manager=device_manager,
            description=description,
            dpcode_wrapper=dpcode_wrapper,
        )
