from __future__ import annotations
from typing import Any
import uuid
import json
from paho.mqtt import (
    client as mqtt,
)
from ..xt_tuya_iot_mq import (
    XTIOTOpenMQ,
)
from ..xt_tuya_iot_openapi import (
    XTIOTOpenAPI,
)


class XTIOTOpenMQIPC(XTIOTOpenMQ):
    def __init__(self, api: XTIOTOpenAPI, class_id: str = "IPC", topics: str = "ipc", link_id: str | None = None) -> None:
        current_link_id: str = link_id if link_id is not None else f"tuya.ipc.{uuid.uuid1()}"
        super().__init__(api, class_id="IPC", topics="ipc", link_id=current_link_id)

    def _on_message(self, mqttc: mqtt.Client, user_data: Any, msg: mqtt.MQTTMessage):
        msg_dict = json.loads(msg.payload.decode("utf8"))
        
        for listener in self.message_listeners:
            listener(msg_dict)
