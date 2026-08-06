"""Entity parser plugin for fdm5kw Tuya irrigation valve controller."""

from __future__ import annotations

from typing import Any

from homeassistant.const import (
    Platform,
)

from ..entity_parser import (
    XTCustomEntityParser,
)
from .sensor import Fdm5kwSensor


def get_plugin_instance() -> XTCustomEntityParser | None:
    return Fdm5kwEntityParser()


class Fdm5kwEntityParser(XTCustomEntityParser):
    def __init__(self) -> None:
        super().__init__()
        Fdm5kwSensor.initialize_sensor()

    def get_descriptors_to_merge(self, platform: Platform) -> Any:
        match platform:
            case Platform.SENSOR:
                return Fdm5kwSensor.get_descriptors_to_merge()
        return None
