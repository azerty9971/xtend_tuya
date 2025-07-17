from __future__ import annotations
from ...const import XTDPCode

INKBIRD_CHANNELS = [
    # (DP_Code,     label, temperature, humidity, battery, enabled_by_default)
    (XTDPCode.CH_0, "ch0", True, True, False, True),  # Base station
    (XTDPCode.CH_1, "ch1", True, False, True, True),
    (XTDPCode.CH_2, "ch2", True, False, True, False),
    (XTDPCode.CH_3, "ch3", True, False, True, False),
    (XTDPCode.CH_4, "ch4", True, False, True, False),
    (XTDPCode.CH_5, "ch5", True, False, True, False),
    (XTDPCode.CH_6, "ch6", True, False, True, False),
    (XTDPCode.CH_7, "ch7", True, False, True, False),
    (XTDPCode.CH_8, "ch8", True, False, True, False),
    (XTDPCode.CH_9, "ch9", True, False, True, False),
]
