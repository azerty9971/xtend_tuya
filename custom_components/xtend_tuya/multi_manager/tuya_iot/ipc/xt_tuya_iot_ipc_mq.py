from __future__ import annotations

from typing import Optional, Any
import uuid
import json
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
        self.mq_config: XTIOTTuyaMQConfig = None
        super().__init__(api)
    
    def _get_mqtt_config(self) -> Optional[XTIOTTuyaMQConfig]:
        if not self.api.is_connect():
            return None
        response = self.api.post(
            TO_C_CUSTOM_MQTT_CONFIG_API
            if (self.api.auth_type == AuthType.CUSTOM)
            else TO_C_SMART_HOME_MQTT_CONFIG_API,
            {
                "uid": self.api.token_info.uid,
                "link_id": f"tuya.ipc.{uuid.uuid1()}",
                "link_type": "mqtt",
                "topics": "ipc",
                "msg_encrypted_version": "2.0"
                if (self.api.auth_type == AuthType.CUSTOM)
                else "1.0",
            },
        )

        if response.get("success", False) is False:
            LOGGER.warning(f"_get_mqtt_config failed: {response}", stack_info=True)
            return None

        return XTIOTTuyaMQConfig(response)
    
    # def _on_connect(self, mqttc: mqtt.Client, user_data: Any, flags, rc: mqtt_ReasonCode, properties: mqtt_Properties | None = None):
    #     if rc == 0:
    #         for (key, value) in self.mq_config.source_topic.items():
    #             mqttc.subscribe(value)
    #     elif rc == 5:
    #         self.__run_mqtt()

    def _on_message(self, mqttc: mqtt.Client, user_data: Any, msg: mqtt.MQTTMessage):
        msg_dict = json.loads(msg.payload.decode("utf8"))
        #LOGGER.warning(f"IPC Message: {msg_dict}")
        for listener in self.message_listeners:
            listener(msg_dict)