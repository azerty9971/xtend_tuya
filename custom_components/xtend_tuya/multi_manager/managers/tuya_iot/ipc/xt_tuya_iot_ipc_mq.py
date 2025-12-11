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
import custom_components.xtend_tuya.multi_manager.managers.tuya_iot.xt_tuya_iot_openapi as iot_api
import custom_components.xtend_tuya.multi_manager.managers.tuya_iot.ipc.xt_tuya_iot_ipc_manager as ipc_man


class XTIOTOpenMQIPC(XTIOTOpenMQ):
    def __init__(self, api: iot_api.XTIOTOpenAPI, manager: ipc_man.XTIOTIPCManager, class_id: str = "IPC", topics: str = "ipc", link_id: str | None = None) -> None:
        current_link_id: str = link_id if link_id is not None else f"tuya.ipc.{uuid.uuid1()}"
        super().__init__(api, manager, class_id="IPC", topics="ipc", link_id=current_link_id)

    def _on_message(self, mqttc: mqtt.Client, user_data: Any, msg: mqtt.MQTTMessage):
        msg_dict = json.loads(msg.payload.decode("utf8"))
        
        for listener in self.message_listeners:
            listener(msg_dict)
