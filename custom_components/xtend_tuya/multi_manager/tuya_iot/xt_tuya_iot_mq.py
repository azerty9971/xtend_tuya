from __future__ import annotations

from typing import Optional, Any
import uuid
import json
from paho.mqtt import client as mqtt
from urllib.parse import urlsplit

import base64

from tuya_iot import (
    TuyaOpenMQ,
    TuyaOpenAPI,
)
from tuya_iot.openmq import (
    TuyaMQConfig,
)

from ...const import (
    LOGGER,  # noqa: F401
)

class XTIOTOpenMQ(TuyaOpenMQ):
    def __init__(self, api: TuyaOpenAPI) -> None:
        super().__init__(api)

    def _get_mqtt_config(self) -> Optional[TuyaMQConfig]:
        if not self.api.is_connect():
            return None
        return super()._get_mqtt_config()

    """def _on_connect(self, mqttc: mqtt.Client, user_data: Any, flags, rc):
        if rc == 0:
            for (key, value) in self.mq_config.source_topic.items():
                LOGGER.warning(f"Subscribing to {value}")
                mqttc.subscribe(value)
        elif rc == CONNECT_FAILED_NOT_AUTHORISED:
            self.__run_mqtt()"""