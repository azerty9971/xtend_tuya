from __future__ import annotations

from ..multi_manager import (
    MultiManager
)

class XTIOTIPCListener:
    def __init__(self, multi_manager: MultiManager) -> None:
        self.multi_manager = multi_manager
    
    