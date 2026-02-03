"""Tuya Open IOT HUB which base on MQTT."""

from __future__ import annotations

import base64
import json
import threading
import time
import uuid
from typing import Any, Callable
from urllib.parse import urlsplit

from Crypto.Cipher import AES
from paho.mqtt import client as mqtt
from paho.mqtt.enums import (
    CallbackAPIVersion as mqtt_CallbackAPIVersion,
)
from paho.mqtt.reasoncodes import (
    ReasonCode as mqtt_ReasonCode,
)
from paho.mqtt.properties import (
    Properties as mqtt_Properties,
)
from paho.mqtt.client import (
    DisconnectFlags as mqtt_DisconnectFlags,
)
from requests.exceptions import RequestException

from .openapi import TuyaOpenAPI
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
        self.url: str = result.get("url", "")
        self.client_id: str = result.get("client_id", "")
        self.username: str = result.get("username", "")
        self.password: str = result.get("password", "")
        self.source_topic: dict[str, str] = result.get("source_topic", {})
        self.sink_topic: dict[str, str] = result.get("sink_topic", {})
        self.expire_time: int = result.get("expire_time", 0)
        self.marked_invalid = False

    def mark_invalid(self) -> None:
        self.marked_invalid = True

    def is_valid(self) -> bool:
        if self.url == "":
            return False
        if self.marked_invalid:
            return False
        return True


class TuyaOpenMQ(threading.Thread):
    """Tuya open iot hub.

    Tuya open iot hub base on mqtt.

    Attributes:
      openapi: tuya openapi
    """

    def __init__(
        self,
        api: TuyaOpenAPI,
        class_id: str = "IOT",
        topics: str = "device",
        link_id: str | None = None,
    ) -> None:
        """Init TuyaOpenMQ."""
        threading.Thread.__init__(self)
        self.api: TuyaOpenAPI = api
        self._stop_event = threading.Event()
        self.client = None
        self.mq_config: TuyaMQConfig = TuyaMQConfig()
        self.message_listeners = set()
        self.link_id: str = link_id if link_id is not None else f"tuya.{uuid.uuid1()}"
        self.class_id: str = class_id
        self.topics: str = topics

    def _get_mqtt_config(self, first_pass=True) -> TuyaMQConfig:
        if self.api.is_connect() is False and self.api.reconnect() is False:
            return TuyaMQConfig()
        if self.api.token_info.is_valid() is False:
            return TuyaMQConfig()

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
        response = self.api.post(path, body)
        if response.get("success", False):
            logger.debug(f"_get_mqtt_config response: {response}")
        else:
            logger.error(f"_get_mqtt_config response: {response}", stack_info=True)

        if response.get("success", False) is False:
            if first_pass:
                self.api.reconnect()
                return self._get_mqtt_config(first_pass=False)
            return TuyaMQConfig()

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
            iv_buffer = buffer[4 : iv_length + 4]

            # get data buffer
            data_buffer = buffer[iv_length + 4 : len(buffer) - GCM_TAG_LENGTH]

            # aad
            aad_buffer = str(t).encode("utf8")

            # tag
            tag_buffer = buffer[len(buffer) - GCM_TAG_LENGTH :]

            cipher = AES.new(key.encode("utf8"), AES.MODE_GCM, nonce=iv_buffer)
            cipher.update(aad_buffer)
            plaintext = cipher.decrypt_and_verify(data_buffer, tag_buffer).decode(
                "utf8"
            )
            return json.loads(plaintext)

    def _on_message(self, mqttc: mqtt.Client, user_data: Any, msg: mqtt.MQTTMessage):
        msg_dict = json.loads(msg.payload.decode("utf8"))
        t = msg_dict.get("t", "")
        mq_config = user_data["mqConfig"]
        decrypted_data = self._decode_mq_message(
            msg_dict["data"], mq_config.password, t
        )
        if decrypted_data is None:
            return

        msg_dict["data"] = decrypted_data
        # logger.debug(f"on_message: {msg_dict}")

        for listener in self.message_listeners:
            listener(msg_dict)

    def _on_log(self, mqttc: mqtt.Client, user_data: Any, level, string):
        # logger.debug(f"_on_log: {string}")
        pass

    def run(self):
        """Method representing the thread's activity which should not be used directly."""
        backoff_seconds = 1
        while not self._stop_event.is_set():
            try:
                self._run_mqtt()
                backoff_seconds = 1

                ## reconnect every 2 hours required.
                #time.sleep(self.mq_config.expire_time - 60)

                # run_mqtt will not do anything if already connected
                time.sleep(30)
            except RequestException as e:
                logger.exception(e)
                logger.error(
                    f"failed to refresh mqtt server, retrying in {backoff_seconds} seconds."
                )

                time.sleep(backoff_seconds)
                backoff_seconds = min(
                    backoff_seconds * 2, 60
                )  # Try at most every 60 seconds to refresh

    def _run_mqtt(self):

        # Don't do anything if already connected
        if self.client and self.client.is_connected():
            return
        
        # if we don't have a valid mq_config, get a new one
        if self.mq_config.is_valid() is False:
            self.mq_config = self._get_mqtt_config()

            # exit if the new mq_config is not valid
            if self.mq_config.is_valid() is False:
                logger.error("error while get mqtt config", stack_info=True)
                return

        # If we have a client, disconnect it first
        if self.client:
            self.client.disconnect()
            self.client = None

        # get a new client
        self.client = self._start()
        if self.client is None:
            self.mq_config.mark_invalid()
            self._run_mqtt()
            return

    # This block will be useful when we'll use Paho MQTT 3.x or above
    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: mqtt_DisconnectFlags,
        rc: mqtt_ReasonCode,
        properties: mqtt_Properties | None = None,
    ):
        if rc != 0:
            logger.error(f"Unexpected disconnection.{rc}")
        # else:
        #    logger.debug("disconnect")

    def _on_connect(
        self,
        mqttc: mqtt.Client,
        user_data: Any,
        flags,
        rc: mqtt_ReasonCode,
        properties: mqtt_Properties | None = None,
    ):
        # logger.debug(f"connect flags->{flags}, rc->{rc}")
        if rc == 0:
            for key, value in self.mq_config.source_topic.items():
                mqttc.subscribe(value)
            logger.debug(f"{self.topics} MQTT connected and subscribed to {self.topics} topics")
        else:
            logger.error(f"MQTT connect failed with rc={rc}")

    def _on_subscribe(
        self,
        mqttc: mqtt.Client,
        user_data: Any,
        mid: int,
        reason_codes: list[mqtt_ReasonCode] = [],
        properties: mqtt_Properties | None = None,
    ):
        # logger.debug(f"_on_subscribe: mid: {mid}, reason_codes: {reason_codes}, properties: {properties}")
        pass

    def _on_publish(
        self,
        mqttc: mqtt.Client,
        user_data: Any,
        mid: int,
        reason_code: mqtt_ReasonCode,
        properties: mqtt_Properties,
    ):
        pass

    def _start(self) -> mqtt.Client | None:      
        mqttc = mqtt.Client(
            callback_api_version=mqtt_CallbackAPIVersion.VERSION2,
            client_id=self.mq_config.client_id,
        )
        mqttc.username_pw_set(self.mq_config.username, self.mq_config.password)
        mqttc.user_data_set({"mqConfig": self.mq_config})
        mqttc.on_connect = self._on_connect
        mqttc.on_message = self._on_message
        mqttc.on_subscribe = self._on_subscribe
        mqttc.on_log = self._on_log
        mqttc.on_disconnect = self._on_disconnect
        mqttc.on_publish = self._on_publish

        url = urlsplit(self.mq_config.url)
        if url.scheme == "ssl":
            mqttc.tls_set()

        if url.hostname is None or url.port is None:
            return None
        mqtt_connection_error = mqttc.connect(url.hostname, url.port)
        if mqtt_connection_error != 0:
            logger.error(f"mqtt connect error: {mqtt_connection_error}")
            return None
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
        if self.client is not None:
            self.client.disconnect()
        self.client = None
        self._stop_event.set()

    def add_message_listener(self, listener: Callable[[dict], None]):
        """Add mqtt message listener."""
        self.message_listeners.add(listener)

    def remove_message_listener(self, listener: Callable[[dict], None]):
        """Remvoe mqtt message listener."""
        self.message_listeners.discard(listener)
