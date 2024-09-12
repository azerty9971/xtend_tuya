from __future__ import annotations

from ..multi_manager import (
    MultiManager
)
from ...const import (
    LOGGER,  # noqa: F401
)
import json

class XTSDPContent:
    answer: dict[str, any]
    candidates: list[dict]

    def __init__(self) -> None:
        self.answer = {}
        self.candidates = []

class XTIOTIPCListener:
    def __init__(self, multi_manager: MultiManager) -> None:
        self.multi_manager = multi_manager
        self.sdp_answers: dict[str, XTSDPContent] = {}
    
    def handle_message(self, msg: str):
        LOGGER.warning(f"Received message from IPC MQTT: {msg}")
        protocol = msg.get("protocol")
        if not protocol:
            return
        LOGGER.warning(f"Prorocol: {protocol}")
        match protocol:
            case 302: #SDP offer/answer/candidate
                data: dict = msg.get("data", {})
                header: dict = data.get("header", {})
                sdp_type = header.get("type")
                session_id = header.get("sessionid")
                msg_content = data.get("msg", {})
                match sdp_type:
                    case "answer":
                        self.sdp_answers[session_id] = XTSDPContent()
                        self.sdp_answers[session_id].answer = msg_content
                        LOGGER.warning(f"Stored SDP answer {session_id} => {msg_content}")
                    case "candidate":
                        self.sdp_answers[session_id].candidates.append(msg_content)
                        LOGGER.warning(f"Stored SDP candidate {session_id} => {msg_content}")