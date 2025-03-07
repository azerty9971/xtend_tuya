from __future__ import annotations

from typing import Any
from homeassistant.const import Platform

from ....ha_tuya_integration.tuya_integration_imports import (
    ALARM_TUYA,
    BINARY_SENSORS_TUYA,
    BUTTONS_TUYA,
    CAMERAS_TUYA,
    CLIMATE_DESCRIPTIONS_TUYA,
    COVERS_TUYA,
    FANS_TUYA,
    HUMIDIFIERS_TUYA,
    LIGHTS_TUYA,
    NUMBERS_TUYA,
    SELECTS_TUYA,
    SENSORS_TUYA,
    SIRENS_TUYA,
    SWITCHES_TUYA
)

def get_tuya_platform_descriptors(platform: Platform) -> Any:
    match platform:
        case Platform.ALARM_CONTROL_PANEL:
            return ALARM_TUYA
        case Platform.BINARY_SENSOR:
            return BINARY_SENSORS_TUYA
        case Platform.BUTTON:
            return BUTTONS_TUYA
        case Platform.CAMERA:
            return list(CAMERAS_TUYA)
        case Platform.CLIMATE:
            return CLIMATE_DESCRIPTIONS_TUYA
        case Platform.COVER:
            return COVERS_TUYA
        case Platform.FAN:
            return FANS_TUYA
        case Platform.HUMIDIFIER:
            return HUMIDIFIERS_TUYA
        case Platform.LIGHT:
            return LIGHTS_TUYA
        case Platform.LOCK:
            return {}
        case Platform.NUMBER:
            return NUMBERS_TUYA
        case Platform.SELECT:
            return SELECTS_TUYA
        case Platform.SENSOR:
            return SENSORS_TUYA
        case Platform.SIREN:
            return SIRENS_TUYA
        case Platform.SWITCH:
            return SWITCHES_TUYA
        case Platform.VACUUM:
            return ["sd"]