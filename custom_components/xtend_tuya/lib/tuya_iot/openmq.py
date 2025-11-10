"""Tuya Open IOT HUB which base on MQTT."""
from __future__ import annotations

import base64
import json
import threading
import time
import uuid
from typing import Any, Callable
from urllib.parse import urlsplit
from typing import Optional

from Crypto.Cipher import AES
from paho.mqtt import client as mqtt
from requests.exceptions import RequestException

from .openapi import TO_C_SMART_HOME_REFRESH_TOKEN_API, TuyaOpenAPI
from .openlogging import logger
from .tuya_enums import AuthType

LINK_ID = f"tuya-iot-app-sdk-python.{uuid.uuid1()}"
GCM_TAG_LENGTH = 16
CONNECT_FAILED_NOT_AUTHORISED = 5

TO_C_CUSTOM_MQTT_CONFIG_API = "/v1.0/iot-03/open-hub/access-config"
TO_C_SMART_HOME_MQTT_CONFIG_API = "/v1.0/open-hub/access/config"


class TuyaMQConfig:
    """Tuya mqtt config."""

    def __init__(self, mqConfigResponse: dict[str, Any] = {}) -> None:
        """Init TuyaMQConfig."""
        result = mqConfigResponse.get("result", {})
        self.url = result.get("url", "")
        self.client_id = result.get("client_id", "")
        self.username = result.get("username", "")
        self.password = result.get("password", "")
        self.source_topic = result.get("source_topic", {})
        self.sink_topic = result.get("sink_topic", {})
        self.expire_time = result.get("expire_time", 0)


class TuyaOpenMQ(threading.Thread):
    """Tuya open iot hub.

    Tuya open iot hub base on mqtt.

    Attributes:
      openapi: tuya openapi
    """

    def __init__(self, api: TuyaOpenAPI) -> None:
        """Init TuyaOpenMQ."""
        threading.Thread.__init__(self)
        self.api: TuyaOpenAPI = api
        self._stop_event = threading.Event()
        self.client = None
        self.mq_config = None
        self.message_listeners = set()

    def _get_mqtt_config(self) -> Optional[TuyaMQConfig]:
        response = self.api.post(
            TO_C_CUSTOM_MQTT_CONFIG_API
            if (self.api.auth_type == AuthType.CUSTOM)
            else TO_C_SMART_HOME_MQTT_CONFIG_API,
            {
                "uid": self.api.token_info.uid,
                "link_id": LINK_ID,
                "link_type": "mqtt",
                "topics": "device",
                "msg_encrypted_version": "2.0"
                if (self.api.auth_type == AuthType.CUSTOM)
                else "1.0",
            },
        )

        if response.get("success", False) is False:
            return None

        return TuyaMQConfig(response)

    def _decode_mq_message(self, b64msg: str, password: str, t: str) -> dict[str, Any]:
        key = password[8:24]

        if self.api.auth_type == AuthType.SMART_HOME:
            cipher = AES.new(key.encode("utf8"), AES.MODE_ECB)
            msg = cipher.decrypt(base64.b64decode(b64msg))
            padding_bytes = msg[-1]
            msg = msg[:-padding_bytes]
            return json.loads(msg)
        else:
            # base64 decode
            buffer = base64.b64decode(b64msg)

            # get iv buffer
            iv_length = int.from_bytes(buffer[0:4], byteorder="big")
            iv_buffer = buffer[4: iv_length + 4]

            # get data buffer
            data_buffer = buffer[iv_length + 4: len(buffer) - GCM_TAG_LENGTH]

            # aad
            aad_buffer = str(t).encode("utf8")

            # tag
            tag_buffer = buffer[len(buffer) - GCM_TAG_LENGTH:]

            cipher = AES.new(key.encode("utf8"), AES.MODE_GCM, nonce=iv_buffer)
            cipher.update(aad_buffer)
            plaintext = cipher.decrypt_and_verify(data_buffer, tag_buffer).decode(
                "utf8"
            )
            return json.loads(plaintext)

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            logger.error(f"Unexpected disconnection.{rc}")
        else:
            logger.debug("disconnect")

    def _on_connect(self, mqttc: mqtt.Client, user_data: Any, flags, rc):
        logger.debug(f"connect flags->{flags}, rc->{rc}")
        if rc == 0:
            for (key, value) in self.mq_config.source_topic.items():
                mqttc.subscribe(value)
        elif rc == CONNECT_FAILED_NOT_AUTHORISED:
            self.__run_mqtt()

    def _on_message(self, mqttc: mqtt.Client, user_data: Any, msg: mqtt.MQTTMessage):
        logger.debug(f"payload-> {msg.payload}")

        msg_dict = json.loads(msg.payload.decode("utf8"))

        t = msg_dict.get("t", "")

        mq_config = user_data["mqConfig"]
        decrypted_data = self._decode_mq_message(
            msg_dict["data"], mq_config.password, t
        )
        if decrypted_data is None:
            return

        msg_dict["data"] = decrypted_data
        logger.debug(f"on_message: {msg_dict}")

        for listener in self.message_listeners:
            listener(msg_dict)

    def _on_subscribe(self, mqttc: mqtt.Client, user_data: Any, mid, granted_qos):
        logger.debug(f"_on_subscribe: {mid}")

    def _on_log(self, mqttc: mqtt.Client, user_data: Any, level, string):
        logger.debug(f"_on_log: {string}")

    def run(self):
        """Method representing the thread's activity which should not be used directly."""
        backoff_seconds = 1
        while not self._stop_event.is_set():
            try:
                self.__run_mqtt()
                backoff_seconds = 1

                # reconnect every 2 hours required.
                time.sleep(self.mq_config.expire_time - 60)
            except RequestException as e:
                logger.exception(e)
                logger.error(f"failed to refresh mqtt server, retrying in {backoff_seconds} seconds.")

                time.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2 , 60) # Try at most every 60 seconds to refresh


    def __run_mqtt(self):
        mq_config = self._get_mqtt_config()
        if mq_config is None:
            logger.error("error while get mqtt config")
            return

        self.mq_config = mq_config

        logger.debug(f"connecting {mq_config.url}")
        mqttc = self._start(mq_config)

        if self.client:
            self.client.disconnect()
        self.client = mqttc

    def _start(self, mq_config: TuyaMQConfig) -> mqtt.Client:
        mqttc = mqtt.Client(mq_config.client_id)
        mqttc.username_pw_set(mq_config.username, mq_config.password)
        mqttc.user_data_set({"mqConfig": mq_config})
        mqttc.on_connect = self._on_connect
        mqttc.on_message = self._on_message
        mqttc.on_subscribe = self._on_subscribe
        mqttc.on_log = self._on_log
        mqttc.on_disconnect = self._on_disconnect

        url = urlsplit(mq_config.url)
        if url.scheme == "ssl":
            mqttc.tls_set()

        mqttc.connect(url.hostname, url.port)

        mqttc.loop_start()
        return mqttc

    def start(self):
        """Start mqtt.

        Start mqtt thread
        """
        logger.debug("start")
        super().start()

    def stop(self):
        """Stop mqtt.

        Stop mqtt thread
        """
        logger.debug("stop")
        self.message_listeners = set()
        self.client.disconnect()
        self.client = None
        self._stop_event.set()

    def add_message_listener(self, listener: Callable[[str], None]):
        """Add mqtt message listener."""
        self.message_listeners.add(listener)

    def remove_message_listener(self, listener: Callable[[str], None]):
        """Remvoe mqtt message listener."""
        self.message_listeners.discard(listener)
