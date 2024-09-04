from __future__ import annotations
from tuya_sharing.mq import (
    SharingMQ,
)

class XTSharingMQ(SharingMQ):
    def subscribe_topic(self, dev_id: str, support_local: bool) -> str:
        subscribe_topic = self.mq_config.dev_topic.format(devId=dev_id)
        if not support_local:
            subscribe_topic += "/pen"
        else:
            subscribe_topic += "/sta"
        return subscribe_topic