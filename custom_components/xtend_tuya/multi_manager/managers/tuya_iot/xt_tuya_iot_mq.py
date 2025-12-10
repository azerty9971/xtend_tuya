from __future__ import annotations
from ....lib.tuya_iot import (
    TuyaOpenMQ,
)
from ....lib.tuya_iot.openmq import (
    TuyaMQConfig,
)
from .xt_tuya_iot_openapi import (
    XTIOTOpenAPI,
)


class XTIOTTuyaMQConfig(TuyaMQConfig):
    pass


class XTIOTOpenMQ(TuyaOpenMQ):
    def __init__(
        self,
        api: XTIOTOpenAPI,
        class_id: str = "IOT",
        topics: str = "device",
        link_id: str | None = None,
    ) -> None:
        super().__init__(
            api=api,
            class_id=class_id,
            topics=topics,
            link_id=link_id,
        )
