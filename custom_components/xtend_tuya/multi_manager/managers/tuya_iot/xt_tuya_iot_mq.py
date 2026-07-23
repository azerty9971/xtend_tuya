from __future__ import annotations

from typing import Any
from paho.mqtt import client as mqtt
from paho.mqtt.reasoncodes import (
    ReasonCode as mqtt_ReasonCode,
)
from paho.mqtt.properties import (
    Properties as mqtt_Properties,
)
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
)
from ....lib.tuya_iot import (
    TuyaOpenMQ,
)
from ....lib.tuya_iot.openmq import (
    TuyaMQConfig,
)
from .xt_tuya_iot_openapi import (
    XTIOTOpenAPI,
)
import custom_components.xtend_tuya.multi_manager.managers.tuya_iot.xt_tuya_iot_manager as man
import custom_components.xtend_tuya.multi_manager.managers.tuya_iot.ipc.xt_tuya_iot_ipc_manager as ipc_man
from ....const import (
    LOGGER,
    DOMAIN,
    XTDeviceWatcherCategory,
    XTDeviceWatcherSpecialDevice,
)


class XTIOTTuyaMQConfig(TuyaMQConfig):
    pass


class XTIOTOpenMQ(TuyaOpenMQ):
    def __init__(
        self,
        api: XTIOTOpenAPI,
        manager: man.XTIOTDeviceManager | ipc_man.XTIOTIPCManager | None = None,
        class_id: str = "IOT",
        topics: str = "device",
        link_id: str | None = None,
    ) -> None:
        super().__init__(
            api=api,
            class_id=class_id,
            topics=topics,
            link_id=link_id,
        )
        self.manager = manager

    def _on_connect(
        self,
        mqttc: mqtt.Client,
        user_data: Any,
        flags,
        rc: mqtt_ReasonCode,
        properties: mqtt_Properties | None = None,
    ):
        if rc == 0:
            for key, value in self.mq_config.source_topic.items():
                error, mid = mqttc.subscribe(value)
                if self.manager is not None and error:
                    self.manager.multi_manager.device_watcher.report_message(
                        XTDeviceWatcherSpecialDevice.NOT_LINKED_TO_A_DEVICE,
                        f"[IOT] Subscribed to topic: {value=} => {error=} {mid=}",
                        XTDeviceWatcherCategory.MQTT,
                    )
        elif rc == 135:  # Not authorized
            LOGGER.error(
                f"[{self.class_id} MQTT] connect failed with rc={rc}, killing this MQTT queue"
            )
            self.stop()
            if self.manager and self.manager.multi_manager:
                self.manager.multi_manager.raise_issue(
                    is_fixable=False,
                    severity=IssueSeverity.ERROR,
                    translation_key="tuya_iot_mqtt_failed_login",
                    translation_placeholders={
                        "name": DOMAIN,
                        "config_entry_id": self.manager.multi_manager.config_entry.title
                        or "Config entry not found",
                    },
                    learn_more_url="https://github.com/azerty9971/xtend_tuya/blob/main/docs/renew_cloud_credentials.md",
                )
        else:
            LOGGER.error(f"[{self.class_id} MQTT] connect failed with rc={rc}")
