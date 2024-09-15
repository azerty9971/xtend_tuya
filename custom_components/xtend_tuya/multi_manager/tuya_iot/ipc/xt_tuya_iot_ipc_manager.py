from __future__ import annotations

import time
import json

from tuya_iot import (
    TuyaOpenAPI,
)

from .xt_tuya_iot_ipc_listener import (
    XTIOTIPCListener,
)
from .xt_tuya_iot_ipc_mq import (
    XTIOTOpenMQIPC,
)

from ...multi_manager import (
    MultiManager,
)
from ....const import (
    LOGGER,
)
from .webrtc.xt_tuya_iot_webrtc_manager import (
    XTIOTWebRTCManager,
)

class XTIOTIPCManager:
    def __init__(self, api: TuyaOpenAPI, multi_manager: MultiManager) -> None:
        self.multi_manager = multi_manager
        self.ipc_mq: XTIOTOpenMQIPC = XTIOTOpenMQIPC(api)
        self.ipc_listener: XTIOTIPCListener = XTIOTIPCListener(self.multi_manager)
        self.ipc_mq.start()
        self.ipc_mq.add_message_listener(self.ipc_listener.handle_message)
        self.api = api
        self.webrtc_manager = XTIOTWebRTCManager()
    
    def get_sdp_answer(self, device_id: str, session_id: str, sdp_offer: str, wait_for_answers: int = 5) -> str | None:
        return self.webrtc_manager.get_sdp_answer(device_id, session_id, sdp_offer, wait_for_answers)

    def _get_from(self) -> str:
        return self.ipc_mq.mq_config.username.split("cloud_")[1]

    def _publish_to_ipc_mqtt(self, topic: str, msg: str):
        publish_result = self.ipc_mq.client.publish(topic=topic, payload=msg)
        publish_result.wait_for_publish(10)