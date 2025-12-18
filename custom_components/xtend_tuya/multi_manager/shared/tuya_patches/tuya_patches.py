from __future__ import annotations
from .models import (
    XTTuyaModelPatcher,
)
from .binary_sensor import (
    XTTuyaBinarySensorPatcher,
)


class XTTuyaPatcher:
    already_patched: bool = False

    @staticmethod
    def patch_tuya_code():
        if XTTuyaPatcher.already_patched is True:
            return
        XTTuyaModelPatcher.patch_tuya()
        XTTuyaBinarySensorPatcher.patch_tuya()
