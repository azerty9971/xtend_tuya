from __future__ import annotations
from ...multi_manager import (
    MultiManager,
)
from .status_helper import (
    StatusHelper,
)


class DebugHelper:
    def __init__(self, multi_manager: MultiManager):
        self.status_helper = StatusHelper(multi_manager)