from __future__ import annotations
from typing import Optional, Any
import uuid
from paho.mqtt import client as mqtt
from urllib.parse import urlsplit
from tuya_iot import (
    TuyaOpenMQ,
)
from tuya_iot.openmq import (
    TuyaMQConfig,
    TO_C_CUSTOM_MQTT_CONFIG_API,
    AuthType,
    TO_C_SMART_HOME_MQTT_CONFIG_API,
    CONNECT_FAILED_NOT_AUTHORISED,
    time,
)
from ...const import (
    LOGGER,  # noqa: F401
)
from .xt_tuya_iot_openapi import (
    XTIOTOpenAPI,
)


class XTIOTTuyaMQConfig(TuyaMQConfig):
    def __init__(self, mqConfigResponse: dict[str, Any] = {}) -> None:
        """Init TuyaMQConfig."""
        self.url: str | None = None
        self.client_id: str | None = None
        self.username: str | None = None
        self.password: str | None = None
        self.source_topic: dict[str, str] | None = None
        self.sink_topic: dict[str, str] | None = None
        self.expire_time: int = 0
        super().__init__(mqConfigResponse)


class XTIOTOpenMQ(TuyaOpenMQ):

    link_id: str | None = None
    class_id: str | None = None
    sleep_time: float | None = None
    topics: str | None = None

    def __init__(self, api: XTIOTOpenAPI) -> None:
        if self.link_id is None:
            self.link_id: str | None = f"tuya.{uuid.uuid1()}"
        if self.class_id is None:
            self.class_id: str | None = "IOT"
        if self.sleep_time is None:
            self.sleep_time: float | None = 0
        if self.topics is None:
            self.topics: str | None = "device"
        super().__init__(api)
        self.api: XTIOTOpenAPI = api  # type: ignore

    def run(self):
        """Method representing the thread's activity which should not be used directly."""
        if self.sleep_time:
            time.sleep(self.sleep_time)
        while not self._stop_event.is_set():
            self.__run_mqtt()

            # reconnect every 2 hours required.
            time.sleep(self.mq_config.expire_time - 60)

    def _get_mqtt_config(self, first_pass=True) -> Optional[XTIOTTuyaMQConfig]:
        # LOGGER.debug(f"[{self.class_id}]Calling _get_mqtt_config")
        if self.api.is_connect() is False and self.api.reconnect() is False:
            # LOGGER.debug(f"_get_mqtt_config failed: not connected", stack_info=True)
            return None
        if self.api.token_info is None:
            return None

        path = (
            TO_C_CUSTOM_MQTT_CONFIG_API
            if (self.api.auth_type == AuthType.CUSTOM)
            else TO_C_SMART_HOME_MQTT_CONFIG_API
        )
        body = {
            "uid": self.api.token_info.uid,
            "link_id": self.link_id,
            "link_type": "mqtt",
            "topics": self.topics,
            "msg_encrypted_version": (
                "2.0" if (self.api.auth_type == AuthType.CUSTOM) else "1.0"
            ),
        }
        # LOGGER.warning(f"Calling {path} => {body}")
        response = self.api.post(path, body)

        if response.get("success", False) is False:
            if first_pass:
                self.api.reconnect()
                return self._get_mqtt_config(first_pass=False)
            return None

        return XTIOTTuyaMQConfig(response)

    # This block will be useful when we'll use Paho MQTT 3.x or above
    # def _on_disconnect(self, client: mqtt.Client, userdata: Any, flags: mqtt_DisconnectFlags, rc: mqtt_ReasonCode, properties: mqtt_Properties | None = None):
    #     super()._on_disconnect(client=client, userdata=userdata, rc=rc.getId())
    #
    # def _on_connect(self, mqttc: mqtt.Client, user_data: Any, flags, rc: mqtt_ReasonCode, properties: mqtt_Properties | None = None):
    #     super()._on_connect(mqttc=mqttc, user_data=user_data,flags=flags, rc=rc)
    #
    # def _on_subscribe(self, mqttc: mqtt.Client, user_data: Any, mid: int, reason_codes: list[mqtt_ReasonCode] = [], properties: mqtt_Properties | None = None):
    #     super()._on_subscribe(mqttc=mqttc, user_data=user_data, mid=mid, granted_qos=None)
    #
    # def _on_publish(self, mqttc: mqtt.Client, user_data: Any, mid: int, reason_code: mqtt_ReasonCode = None, properties: mqtt_Properties = None):
    #     pass

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            LOGGER.error(f"Unexpected disconnection.{rc}")
        else:
            LOGGER.debug("disconnect")

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

    def _on_connect(self, mqttc: mqtt.Client, user_data: Any, flags, rc):
        # LOGGER.debug(f"connect flags->{flags}, rc->{rc}")
        if rc == 0:
            if self.mq_config.source_topic is not None:
                for key, value in self.mq_config.source_topic.items():
                    mqttc.subscribe(value)
        elif rc == CONNECT_FAILED_NOT_AUTHORISED:
            self.__run_mqtt()

    def __run_mqtt(self):
        mq_config = self._get_mqtt_config()
        if mq_config is None:
            LOGGER.error("error while get mqtt config", stack_info=True)
            return

        self.mq_config = mq_config

        # LOGGER.debug(f"connecting {mq_config.url}")
        mqttc = self._start(mq_config)

        if self.client:
            self.client.disconnect()
        self.client = mqttc
