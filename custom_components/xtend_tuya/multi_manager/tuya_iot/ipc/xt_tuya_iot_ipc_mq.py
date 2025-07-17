from __future__ import annotations
from typing import Any
import uuid
import json
from paho.mqtt import (
    client as mqtt,
)
from urllib.parse import urlsplit
from ..xt_tuya_iot_mq import (
    XTIOTOpenMQ,
    XTIOTTuyaMQConfig,
    TuyaMQConfig,
)
from ..xt_tuya_iot_openapi import (
    XTIOTOpenAPI,
)
from ....const import LOGGER  # noqa: F401


class XTIOTOpenMQIPC(XTIOTOpenMQ):
    def __init__(self, api: XTIOTOpenAPI) -> None:
        self.sleep_time: float | None = (
            None  # Debug value to have a time between IPC and IOT queries for log reading
        )
        self.mq_config: XTIOTTuyaMQConfig | None = None
        self.link_id: str | None = f"tuya.ipc.{uuid.uuid1()}"
        self.class_id: str | None = "IPC"
        self.topics: str | None = "ipc"
        super().__init__(api)

    def _on_message(self, mqttc: mqtt.Client, user_data: Any, msg: mqtt.MQTTMessage):
        msg_dict = json.loads(msg.payload.decode("utf8"))
        for listener in self.message_listeners:
            listener(msg_dict)

    def _start(self, mq_config: TuyaMQConfig) -> mqtt.Client:
        # mqttc = mqtt.Client(callback_api_version=mqtt_CallbackAPIVersion.VERSION2 ,client_id=mq_config.client_id)
        mqttc = mqtt.Client(client_id=mq_config.client_id)
        mqttc.username_pw_set(mq_config.username, mq_config.password)
        mqttc.user_data_set({"mqConfig": mq_config})
        mqttc.on_connect = self._on_connect
        mqttc.on_message = self._on_message
        mqttc.on_subscribe = self._on_subscribe
        mqttc.on_log = self._on_log
        # mqttc.on_publish = self._on_publish
        mqttc.on_disconnect = self._on_disconnect

        url = urlsplit(mq_config.url)
        if url.scheme == "ssl":
            mqttc.tls_set()

        mqttc.connect(url.hostname, url.port)

        mqttc.loop_start()
        return mqttc
