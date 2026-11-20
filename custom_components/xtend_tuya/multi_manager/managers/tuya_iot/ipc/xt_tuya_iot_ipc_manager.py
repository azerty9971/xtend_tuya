from __future__ import annotations
from ....multi_manager import (
    MultiManager,
)
from ..xt_tuya_iot_openapi import (
    XTIOTOpenAPI,
)
import custom_components.xtend_tuya.multi_manager.managers.tuya_iot.ipc.xt_tuya_iot_ipc_listener as ipc
from .xt_tuya_iot_ipc_mq import (
    XTIOTOpenMQIPC,
)
import custom_components.xtend_tuya.multi_manager.managers.tuya_iot.ipc.webrtc.xt_tuya_iot_webrtc_manager as webrtc_man
from .....const import (
    XTDeviceWatcherCategory,
    XTDeviceWatcherSpecialDevice,
)


class XTIOTIPCManager:  # noqa: F811
    def __init__(self, api: XTIOTOpenAPI, non_user_api: XTIOTOpenAPI, multi_manager: MultiManager) -> None:
        self.multi_manager = multi_manager
        self.mq: XTIOTOpenMQIPC = XTIOTOpenMQIPC(api, self)
        self.ipc_listener: ipc.XTIOTIPCListener = ipc.XTIOTIPCListener(self)
        self.mq.start()
        self.mq.add_message_listener(self.ipc_listener.handle_message)
        self.api = api
        self.non_user_api = non_user_api
        self.webrtc_manager = webrtc_man.XTIOTWebRTCManager(self)

    def get_from(self) -> str | None:
        if self.mq.mq_config is None or self.mq.mq_config.username is None:
            return None
        return self.mq.mq_config.username.split("cloud_")[1]

    def report_message(
        self,
        msg: str,
        device_id: str = XTDeviceWatcherSpecialDevice.NOT_LINKED_TO_A_DEVICE,
        category: XTDeviceWatcherCategory = XTDeviceWatcherCategory.WEBRTC,
        print_stack: bool = False,
        method: str = "debug",
    ) -> None:
        self.multi_manager.device_watcher.report_message(
            dev_id=device_id,
            message=msg,
            category=category,
            print_stack=print_stack,
            method=method,
        )

    def publish_to_ipc_mqtt(
        self,
        topic: str,
        msg: str,
        device_id: str = XTDeviceWatcherSpecialDevice.NOT_LINKED_TO_A_DEVICE,
    ):
        if self.mq.client is None:
            self.report_message(
                f"IPC MQTT publish DROPPED, client is None (MQTT thread is not running): topic={topic}",
                device_id=device_id,
                method="warning",
            )
            return
        if self.mq.client.is_connected() is False:
            self.report_message(
                f"IPC MQTT publish DROPPED, client is not connected: topic={topic}",
                device_id=device_id,
                method="warning",
            )
            return
        publish_result = self.mq.client.publish(topic=topic, payload=msg)
        if publish_result.rc != 0:
            self.report_message(
                f"IPC MQTT publish FAILED with rc={publish_result.rc}: topic={topic}",
                device_id=device_id,
                method="warning",
            )
            return
        publish_result.wait_for_publish(10)

    def refresh_mq(self):
        self.mq.stop()
        self.mq = XTIOTOpenMQIPC(self.api, self)
        self.mq.add_message_listener(self.ipc_listener.handle_message)
        self.mq.start()
