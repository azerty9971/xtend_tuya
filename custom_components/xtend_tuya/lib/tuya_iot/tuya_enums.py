"""Tuya iot enums."""

from enum import Enum


class AuthType(Enum):
    """Tuya Cloud Auth Type."""

    SMART_HOME = 0
    CUSTOM = 1


class TuyaCloudOpenAPIEndpoint:
    """Tuya Cloud Open API Endpoint."""

    CHINA = "https://openapi.tuyacn.com"
    AMERICA = "https://openapi.tuyaus.com"
    AMERICA_AZURE = "https://openapi-ueaz.tuyaus.com"
    EUROPE = "https://openapi.tuyaeu.com"
    EUROPE_MS = "https://openapi-weaz.tuyaeu.com"
    INDIA = "https://openapi.tuyain.com"
