from __future__ import annotations

from ..multi_manager import (
    MultiManager
)
from ...const import (
    LOGGER,  # noqa: F401
)

class XTIOTIPCListener:
    def __init__(self, multi_manager: MultiManager) -> None:
        self.multi_manager = multi_manager
    
    def forward_message_to_multi_manager(self, msg:str):
        LOGGER.warning(f"Received message from IPC MQTT: {msg}")