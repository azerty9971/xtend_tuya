"""Entity parser plugin for the dé EV charger (category "qt", vendor "x_" DPCodes).

The descriptors only match devices reporting these vendor specific DPCodes.
"""

from __future__ import annotations
from typing import Any
from homeassistant.const import (
    Platform,
)
from ..entity_parser import (
    XTCustomEntityParser,
)
from .button import DE_EV_CHARGER_BUTTONS
from .number import DE_EV_CHARGER_NUMBERS
from .sensor import DE_EV_CHARGER_SENSORS
from .switch import DE_EV_CHARGER_SWITCHES


def get_plugin_instance() -> XTCustomEntityParser | None:
    return DeEVChargerEntityParser()


class DeEVChargerEntityParser(XTCustomEntityParser):
    def get_descriptors_to_merge(self, platform: Platform) -> Any:
        match platform:
            case Platform.SENSOR:
                return DE_EV_CHARGER_SENSORS
            case Platform.SWITCH:
                return DE_EV_CHARGER_SWITCHES
            case Platform.NUMBER:
                return DE_EV_CHARGER_NUMBERS
            case Platform.BUTTON:
                return DE_EV_CHARGER_BUTTONS
        return None
