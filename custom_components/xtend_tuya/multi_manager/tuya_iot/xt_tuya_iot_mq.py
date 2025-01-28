from __future__ import annotations

from typing import Optional, Any
import uuid

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
                "link_id": f"tuya-iot-app-sdk-python.{uuid.uuid1()}",
                "link_type": "mqtt",
                "topics": "ipc",
                "msg_encrypted_version": "2.0"
                if (self.api.auth_type == AuthType.CUSTOM)
                else "1.0",
            },
        )

        if response.get("success", False) is False:
            LOGGER.debug(f"_get_mqtt_config failed: {response}", stack_info=True)
            return None

        return XTIOTTuyaMQConfig(response)

    """def _on_connect(self, mqttc: mqtt.Client, user_data: Any, flags, rc):
        if rc == 0:
            for (key, value) in self.mq_config.source_topic.items():
                LOGGER.warning(f"Subscribing to {value}")
                mqttc.subscribe(value)
        elif rc == CONNECT_FAILED_NOT_AUTHORISED:
            self.__run_mqtt()"""