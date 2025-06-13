from __future__ import annotations

from typing import Any

from homeassistant.const import (
    Platform,
)

from ..entity_parser import (
    XTCustomEntityParser,
)

def get_plugin_instance(platform: Platform) -> XTCustomEntityParser | None:
    return InkbirdEntityParser()

class InkbirdEntityParser(XTCustomEntityParser):
    def __init__(self) -> None:
        super().__init__()
        InkbirdSensor.initialize_sensor()

    def get_descriptors_to_merge(self, platform: Platform) -> Any:
        match platform:
            case Platform.SENSOR:
                return InkbirdSensor.get_descriptors_to_merge()
        return None
    
from .sensor import (
    InkbirdSensor
)