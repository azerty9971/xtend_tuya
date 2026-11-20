from __future__ import annotations
import custom_components.xtend_tuya.multi_manager.managers.tuya_iot.ipc.xt_tuya_iot_ipc_manager as ipc_man
from .....const import (
    XTDeviceWatcherCategory,
)


class XTIOTIPCListener:
    def __init__(self, ipc_manager: ipc_man.XTIOTIPCManager) -> None:
        self.ipc_manager = ipc_manager

    def handle_message(self, msg: dict):
        protocol = msg.get("protocol")
        if not protocol:
            return
        match protocol:
            case 302:  # SDP offer/answer/candidate
                data: dict = msg.get("data", {})
                if not isinstance(data, dict):
                    self.ipc_manager.report_message(
                        f"IPC message 302 with unexpected data type: {msg}",
                        category=XTDeviceWatcherCategory.WEBRTC,
                        method="warning",
                    )
                    return
                header: dict = data.get("header", {})
                sdp_type = header.get("type")
                session_id = header.get("sessionid")
                msg_content = data.get("msg", {})
                match sdp_type:
                    case "answer":
                        self.ipc_manager.webrtc_manager.set_sdp_answer(
                            session_id, msg_content
                        )
                    case "candidate":
                        self.ipc_manager.webrtc_manager.add_sdp_answer_candidate(
                            session_id, msg_content
                        )
            case _:
                self.ipc_manager.report_message(
                    f"IPC message with unhandled protocol received: {msg}",
                    category=XTDeviceWatcherCategory.WEBRTC,
                    method="warning",
                )
