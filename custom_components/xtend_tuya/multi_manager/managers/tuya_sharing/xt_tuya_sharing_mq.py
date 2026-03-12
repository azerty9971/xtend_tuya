from __future__ import annotations
import json
from typing import Any
from tuya_sharing.mq import (
    SharingMQ,
    SharingMQConfig,
    CustomerApi,
    CustomerDevice,
)
from paho.mqtt import client as mqtt
import custom_components.xtend_tuya.multi_manager.managers.tuya_sharing.xt_tuya_sharing_manager as sm
from ....const import (
    LOGGER,
)

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
    # This block will be useful when we'll use Paho MQTT 3.x or above
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

    def __init__(
        self,
        customer_api: CustomerApi,
        owner_ids: list,
        device: list[sm.XTDevice],
        manager: sm.XTSharingDeviceManager,
    ):
        super().__init__(
            customer_api,
            owner_ids,
            device,  # type: ignore
        )
        self.manager = manager
        self.shutting_down = False

    def subscribe_device(self, dev_id: str, device: CustomerDevice):
        if device is None:
            return
        self.device.append(device)
        self.subscribe_to_mqtt_topics(dev_id)
    
    def un_subscribe_device(self, dev_id: str, support_local: bool):
        topic1 = self.subscribe_topic(dev_id, True)
        topic2 = self.subscribe_topic(dev_id, False)
        if self.client is not None:
            self.client.unsubscribe([topic1, topic2])

    def _start(self, mq_config: SharingMQConfig) -> mqtt.Client:
        # mqttc = mqtt.Client(callback_api_version=mqtt_CallbackAPIVersion.VERSION2, client_id=mq_config.client_id)
        mqttc = mqtt.Client(client_id=mq_config.client_id)
        mqttc.username_pw_set(mq_config.username, mq_config.password)
        mqttc.user_data_set({"mqConfig": mq_config})
        mqttc.on_connect = self._on_connect
        mqttc.on_message = self._on_message
        mqttc.on_subscribe = self._on_subscribe
        # mqttc.on_publish = self._on_publish
        mqttc.on_log = self._on_log
        mqttc.on_disconnect = self._on_disconnect

        url = urlsplit(mq_config.url)
        if url.scheme == "ssl":
            mqttc.tls_set()

        mqttc.connect(url.hostname, url.port)

        mqttc.loop_start()
        return mqttc

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            if self.shutting_down is False:
                self.shutting_down = True
                LOGGER.warning("Unexpected disconnection. Reconnecting...")
                self.manager.refresh_mq()
        else:
            LOGGER.debug("disconnect")
    
    def _on_message(self, mqttc: mqtt.Client, user_data: Any, msg: mqtt.MQTTMessage):
        msg_dict = json.loads(msg.payload.decode("utf8"))

        # LOGGER.warning(f"[SHARING MQTT]({self.uuid})on_message: {msg_dict}, user_data: {user_data}")

        for listener in self.message_listeners:
            listener(msg_dict)
    
    def subscribe_to_mqtt_topics(self, dev_id: str) -> None:
        topic1 = self.subscribe_topic(dev_id, True)
        topic2 = self.subscribe_topic(dev_id, False)
        if self.client is not None:
            self.client.subscribe([(topic1, 0), (topic2, 0)])

    def _on_connect(self, mqttc: mqtt.Client, user_data: Any, flags, rc):
        if rc == 0:
            if self.mq_config is None:
                return
            for owner_id in self.owner_ids:
                mqttc.subscribe(self.mq_config.owner_topic.format(ownerId=owner_id))
            batch_size = 10
            for i in range(0, len(self.device), batch_size):
                batch_devices = self.device[i:i + batch_size]
                topics_to_subscribe = []
                for dev in batch_devices:
                    dev_id = dev.id
                    topic_str = self.subscribe_topic(dev_id, False)
                    topics_to_subscribe.append((topic_str, 0))  # 指定主题和qos=0
                    topic_str = self.subscribe_topic(dev_id, True)
                    topics_to_subscribe.append((topic_str, 0))  # 指定主题和qos=0

                if topics_to_subscribe:
                    mqttc.subscribe(topics_to_subscribe)
        else:
            super()._on_connect(mqttc, user_data, flags, rc)
