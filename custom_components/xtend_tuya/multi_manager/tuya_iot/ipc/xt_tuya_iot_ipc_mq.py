from __future__ import annotations

from typing import Optional, Any
import uuid
import json
from paho.mqtt import (
    client as mqtt,
)
from paho.mqtt.enums import (
    CallbackAPIVersion as mqtt_CallbackAPIVersion,
)
from paho.mqtt.reasoncodes import (
    ReasonCode as mqtt_ReasonCode,
)
from paho.mqtt.properties import (
    Properties as mqtt_Properties,
)
from urllib.parse import urlsplit

from tuya_iot.openmq import (
    TuyaMQConfig,
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
                "link_id": f"tuya-iot-app-sdk-python.ipc.{uuid.uuid1()}",
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
    
    def _on_connect(self, mqttc: mqtt.Client, user_data: Any, flags, rc: mqtt_ReasonCode, properties: mqtt_Properties | None = None):
        if rc == 0:
            for (key, value) in self.mq_config.source_topic.items():
                mqttc.subscribe(value)
        elif rc == 5:
            self.__run_mqtt()

    def _on_message(self, mqttc: mqtt.Client, user_data: Any, msg: mqtt.MQTTMessage):
        msg_dict = json.loads(msg.payload.decode("utf8"))
        #LOGGER.warning(f"IPC Message: {msg_dict}")
        for listener in self.message_listeners:
            listener(msg_dict)
    
    def _on_subscribe(self, mqttc: mqtt.Client, user_data: Any, mid: int, reason_codes: list[mqtt_ReasonCode] = [], properties: mqtt_Properties | None = None):
        #LOGGER.debug(f"_on_subscribe: {mid}")
        pass
    
    def _on_publish(self, mqttc: mqtt.Client, user_data: Any, mid: int, reason_code: mqtt_ReasonCode = None, properties: mqtt_Properties = None):
        #LOGGER.debug(f"_on_publish: {mid} <=> {user_data}")
        pass

    def _start(self, mq_config: TuyaMQConfig) -> mqtt.Client:
        mqttc = mqtt.Client(callback_api_version=mqtt_CallbackAPIVersion.VERSION2, client_id=mq_config.client_id)
        mqttc.username_pw_set(mq_config.username, mq_config.password)
        mqttc.user_data_set({"mqConfig": mq_config})
        mqttc.on_connect = self._on_connect
        mqttc.on_message = self._on_message
        mqttc.on_subscribe = self._on_subscribe
        mqttc.on_log = self._on_log
        mqttc.on_disconnect = self._on_disconnect
        mqttc.on_publish = self._on_publish

        url = urlsplit(mq_config.url)
        if url.scheme == "ssl":
            mqttc.tls_set()

        mqttc.connect(url.hostname, url.port)

        mqttc.loop_start()
        return mqttc