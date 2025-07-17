from __future__ import annotations
import custom_components.xtend_tuya.multi_manager.multi_manager as mm
from .status_helper import (
    StatusHelper,
)


class DebugHelper:
    def __init__(self, multi_manager: mm.MultiManager):
        self.status_helper = StatusHelper(multi_manager)
