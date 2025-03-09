from __future__ import annotations

from typing import Any

from tuya_sharing.mq import (
    SharingMQ,
    SharingMQConfig
)

from paho.mqtt import client as mqtt
# from paho.mqtt.enums import (
#     CallbackAPIVersion as mqtt_CallbackAPIVersion,
# )
# from paho.mqtt.client import (
#     DisconnectFlags as mqtt_DisconnectFlags,
# )
# from paho.mqtt.reasoncodes import (
#     ReasonCode as mqtt_ReasonCode,
# )
# from paho.mqtt.properties import (
#     Properties as mqtt_Properties,
# )
from urllib.parse import urlsplit

class XTSharingMQ(SharingMQ):

    #This block will be useful when we'll use Paho MQTT 3.x or above
    # def _on_disconnect(self, client: mqtt.Client, userdata: Any, flags: mqtt_DisconnectFlags, rc: mqtt_ReasonCode, properties: mqtt_Properties | None = None):
    #     super()._on_disconnect(client=client, userdata=userdata, rc=rc)
    #
    # def _on_connect(self, mqttc: mqtt.Client, user_data: Any, flags, rc: mqtt_ReasonCode, properties: mqtt_Properties | None = None):
    #     super()._on_connect(mqttc=mqttc, user_data=user_data,flags=flags, rc=rc)
    #
    # def _on_subscribe(self, mqttc: mqtt.Client, user_data: Any, mid: int, reason_codes: list[mqtt_ReasonCode] = [], properties: mqtt_Properties | None = None):
    #     super()._on_subscribe(mqttc=mqttc, user_data=user_data, mid=mid, granted_qos=None)
    #
    # def _on_publish(self, mqttc: mqtt.Client, user_data: Any, mid: int, reason_code: mqtt_ReasonCode = None, properties: mqtt_Properties = None):
    #     pass

    def _start(self, mq_config: SharingMQConfig) -> mqtt.Client:
        #mqttc = mqtt.Client(callback_api_version=mqtt_CallbackAPIVersion.VERSION2, client_id=mq_config.client_id)
        mqttc = mqtt.Client(client_id=mq_config.client_id)
        mqttc.username_pw_set(mq_config.username, mq_config.password)
        mqttc.user_data_set({"mqConfig": mq_config})
        mqttc.on_connect = self._on_connect
        mqttc.on_message = self._on_message
        mqttc.on_subscribe = self._on_subscribe
        #mqttc.on_publish = self._on_publish
        mqttc.on_log = self._on_log
        mqttc.on_disconnect = self._on_disconnect

        url = urlsplit(mq_config.url)
        if url.scheme == "ssl":
            mqttc.tls_set()

        mqttc.connect(url.hostname, url.port)

        mqttc.loop_start()
        return mqttc