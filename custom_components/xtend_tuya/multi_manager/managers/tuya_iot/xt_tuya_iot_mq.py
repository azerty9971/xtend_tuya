from __future__ import annotations
from typing import Any
import uuid
from paho.mqtt import client as mqtt
from urllib.parse import urlsplit
from ....lib.tuya_iot import (
    TuyaOpenMQ,
)
from ....lib.tuya_iot.openmq import (
    TuyaMQConfig,
    TO_C_CUSTOM_MQTT_CONFIG_API,
    AuthType,
    TO_C_SMART_HOME_MQTT_CONFIG_API,
    CONNECT_FAILED_NOT_AUTHORISED,
    time,
)
from ....const import (
    LOGGER,
)
from .xt_tuya_iot_openapi import (
    XTIOTOpenAPI,
)


class XTIOTTuyaMQConfig(TuyaMQConfig):
    pass


class XTIOTOpenMQ(TuyaOpenMQ):
    def __init__(self, api: XTIOTOpenAPI, class_id: str = "IOT", topics: str = "device", link_id: str | None = None) -> None:
        super().__init__(api=api, class_id=class_id, topics=topics, link_id=link_id)
