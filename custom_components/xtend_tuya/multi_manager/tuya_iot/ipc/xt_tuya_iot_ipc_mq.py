from __future__ import annotations

from typing import Optional, Any
import uuid
import json
import time
from paho.mqtt import (
    client as mqtt,
)
from urllib.parse import urlsplit

from tuya_iot.openmq import (
    TO_C_CUSTOM_MQTT_CONFIG_API,
    AuthType,
    TO_C_SMART_HOME_MQTT_CONFIG_API,
)

from tuya_iot import (
    TuyaOpenAPI,
)

from ..xt_tuya_iot_mq import (
    XTIOTOpenMQ,
    XTIOTTuyaMQConfig,
)

from ....const import (
    LOGGER  # noqa: F401
)



class XTIOTOpenMQIPC(XTIOTOpenMQ):
    def __init__(self, api: TuyaOpenAPI) -> None:
        time.sleep(5)   #Debug value to have a time between IPC and IOT queries for log reading
        self.mq_config: XTIOTTuyaMQConfig = None
        self.link_id: str = f"tuya.ipc.{uuid.uuid1()}"
        self.class_id: str = "IPC"
        super().__init__(api)

    def _on_message(self, mqttc: mqtt.Client, user_data: Any, msg: mqtt.MQTTMessage):
        msg_dict = json.loads(msg.payload.decode("utf8"))
        #LOGGER.warning(f"IPC Message: {msg_dict}")
        for listener in self.message_listeners:
            listener(msg_dict)