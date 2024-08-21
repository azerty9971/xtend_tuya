from __future__ import annotations

from typing import Any, Optional

from tuya_iot import (
    TuyaOpenMQ,
    TuyaOpenAPI,
)

from tuya_iot.openmq import (
    CONNECT_FAILED_NOT_AUTHORISED,
    mqtt,
    TuyaMQConfig,
    TO_C_CUSTOM_MQTT_CONFIG_API,
    AuthType,
    TO_C_SMART_HOME_MQTT_CONFIG_API,
    LINK_ID
)

from ...const import (
    LOGGER,
)

class XTIOTOpenMQ(TuyaOpenMQ):
    def __init__(self, api: TuyaOpenAPI) -> None:
        super().__init__(api)

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
        
        LOGGER.warning(f"_get_mqtt_config => {response}")

        return TuyaMQConfig(response)

    def _on_connect(self, mqttc: mqtt.Client, user_data: Any, flags, rc):
        if rc == 0:
            for (key, value) in self.mq_config.source_topic.items():
                LOGGER.warning(f"Subscribing tp {value}")
                mqttc.subscribe(value)
        elif rc == CONNECT_FAILED_NOT_AUTHORISED:
            self.__run_mqtt()