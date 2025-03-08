from __future__ import annotations

from typing import Optional, Any
import uuid

from paho.mqtt import client as mqtt
from paho.mqtt.enums import (
    CallbackAPIVersion as mqtt_CallbackAPIVersion,
)
from paho.mqtt.client import (
    DisconnectFlags as mqtt_DisconnectFlags,
)
from paho.mqtt.reasoncodes import (
    ReasonCode as mqtt_ReasonCode,
)
from paho.mqtt.properties import (
    Properties as mqtt_Properties,
)
from urllib.parse import urlsplit

from tuya_iot import (
    TuyaOpenMQ,
    TuyaOpenAPI,
)
from tuya_iot.openmq import (
    TuyaMQConfig,
    TO_C_CUSTOM_MQTT_CONFIG_API,
    AuthType,
    TO_C_SMART_HOME_MQTT_CONFIG_API,
)

from ...const import (
    LOGGER,  # noqa: F401
)

class XTIOTTuyaMQConfig(TuyaMQConfig):
    def __init__(self, mqConfigResponse: dict[str, Any] = {}) -> None:
        """Init TuyaMQConfig."""
        self.url: str = None
        self.client_id: str = None
        self.username: str = None
        self.password: str = None
        self.source_topic: dict = None
        self.sink_topic: dict = None
        self.expire_time: int = 0
        super().__init__(mqConfigResponse)

class XTIOTOpenMQ(TuyaOpenMQ):
    def __init__(self, api: TuyaOpenAPI) -> None:
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
                "link_id": f"tuya.{uuid.uuid1()}",
                "link_type": "mqtt",
                "topics": "device",
                "msg_encrypted_version": "2.0"
                if (self.api.auth_type == AuthType.CUSTOM)
                else "1.0",
            },
        )

        if response.get("success", False) is False:
            LOGGER.debug(f"_get_mqtt_config failed: {response}", stack_info=True)
            return None

        return XTIOTTuyaMQConfig(response)

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, flags: mqtt_DisconnectFlags, rc: mqtt_ReasonCode, properties: mqtt_Properties | None = None):
        super()._on_disconnect(client=client, userdata=userdata, rc=rc.getId())

    def _on_connect(self, mqttc: mqtt.Client, user_data: Any, flags, rc: mqtt_ReasonCode, properties: mqtt_Properties | None = None):
        super()._on_connect(mqttc=mqttc, user_data=user_data,flags=flags, rc=rc)

    def _on_subscribe(self, mqttc: mqtt.Client, user_data: Any, mid: int, reason_codes: list[mqtt_ReasonCode] = [], properties: mqtt_Properties | None = None):
        super()._on_subscribe(mqttc=mqttc, user_data=user_data, mid=mid, granted_qos=None)

    def _on_publish(self, mqttc: mqtt.Client, user_data: Any, mid: int, reason_code: mqtt_ReasonCode = None, properties: mqtt_Properties = None):
        pass

    def _start(self, mq_config: TuyaMQConfig) -> mqtt.Client:
        mqttc = mqtt.Client(callback_api_version=mqtt_CallbackAPIVersion.VERSION2 ,client_id=mq_config.client_id)
        mqttc.username_pw_set(mq_config.username, mq_config.password)
        mqttc.user_data_set({"mqConfig": mq_config})
        mqttc.on_connect = self._on_connect
        mqttc.on_message = self._on_message
        mqttc.on_subscribe = self._on_subscribe
        mqttc.on_log = self._on_log
        mqttc.on_publish = self._on_publish
        mqttc.on_disconnect = self._on_disconnect

        url = urlsplit(mq_config.url)
        if url.scheme == "ssl":
            mqttc.tls_set()

        mqttc.connect(url.hostname, url.port)

        mqttc.loop_start()
        return mqttc

    """def _on_connect(self, mqttc: mqtt.Client, user_data: Any, flags, rc):
        if rc == 0:
            for (key, value) in self.mq_config.source_topic.items():
                LOGGER.warning(f"Subscribing to {value}")
                mqttc.subscribe(value)
        elif rc == CONNECT_FAILED_NOT_AUTHORISED:
            self.__run_mqtt()"""