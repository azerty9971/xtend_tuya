from __future__ import annotations

from ..multi_manager import (
    MultiManager,
)

class MultiMQTTQueue:
    def __init__(self, multi_manager: MultiManager) -> None:
        self.multi_manager = multi_manager

    def stop(self) -> None:
        if (
                self.multi_manager.sharing_account 
                and self.multi_manager.sharing_account.device_manager 
                and self.multi_manager.sharing_account.device_manager.mq 
                and not self.multi_manager.reuse_config
        ):
            self.multi_manager.sharing_account.device_manager.mq.stop()
        if self.multi_manager.iot_account and self.multi_manager.iot_account.device_manager and self.multi_manager.iot_account.device_manager.mq:
            self.multi_manager.iot_account.device_manager.mq.stop()