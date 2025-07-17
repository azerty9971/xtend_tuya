from __future__ import annotations
import custom_components.xtend_tuya.multi_manager.multi_manager as mm


class MultiMQTTQueue:
    def __init__(self, multi_manager: mm.MultiManager) -> None:
        self.multi_manager = multi_manager

    def stop(self) -> None:
        for account in self.multi_manager.accounts.values():
            account.on_mqtt_stop()
