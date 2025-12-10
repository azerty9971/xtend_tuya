from __future__ import annotations
from typing import Any
from paho.mqtt.reasoncodes import (
    ReasonCode as mqtt_ReasonCode,
)
from paho.mqtt.properties import (
    Properties as mqtt_Properties,
)
from paho.mqtt.client import (
    DisconnectFlags as mqtt_DisconnectFlags,
)
from paho.mqtt import client as mqtt

from ....lib.tuya_iot import (
    TuyaOpenMQ,
)
from ....lib.tuya_iot.openmq import (
    TuyaMQConfig,
)
from .xt_tuya_iot_openapi import (
    XTIOTOpenAPI,
)
from .xt_tuya_iot_manager import (
    XTIOTDeviceManager,
)
from ....const import (
    LOGGER,  # noqa: F401
)


class XTIOTTuyaMQConfig(TuyaMQConfig):
    pass


class XTIOTOpenMQ(TuyaOpenMQ):
    def __init__(
        self,
        api: XTIOTOpenAPI,
        manager: XTIOTDeviceManager,
        class_id: str = "IOT",
        topics: str = "device",
        link_id: str | None = None,
    ) -> None:
        super().__init__(
            api=api,
            class_id=class_id,
            topics=topics,
            link_id=link_id,
        )
        self.manager = manager
    
    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: mqtt_DisconnectFlags,
        rc: mqtt_ReasonCode,
        properties: mqtt_Properties | None = None,
    ):
        if rc != 0:
            LOGGER.info("MQ disconnected unexpectedly, reconnecting...")
            self.manager.refresh_mq()
