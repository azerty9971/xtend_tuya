from __future__ import annotations
from .binary_sensor import (
    XTTuyaBinarySensorPatcher,  # noqa: F401
)


class XTTuyaPatcher:
    already_patched: bool = False

    @staticmethod
    def patch_tuya_code():
        if XTTuyaPatcher.already_patched is True:
            return
        XTTuyaPatcher.already_patched = True
        #XTTuyaModelPatcher.patch_tuya()
        #XTTuyaBinarySensorPatcher.patch_tuya()
