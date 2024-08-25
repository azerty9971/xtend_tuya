from __future__ import annotations

from ..multi_manager import (
    MultiManager,
)

class MultiMQTTQueue:
    def __init__(self, multi_manager: MultiManager) -> None:
        self.multi_manager = multi_manager

    def stop(self) -> None:
        for account in self.multi_manager.accounts.values():
            account.on_mqtt_stop()
        if self.multi_manager.iot_account and self.multi_manager.iot_account.device_manager and self.multi_manager.iot_account.device_manager.mq:
            self.multi_manager.iot_account.device_manager.mq.stop()