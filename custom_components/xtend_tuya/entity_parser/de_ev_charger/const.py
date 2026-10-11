"""Constants for the dé EV charger (category "qt", vendor specific "x_" DPCodes)."""

from __future__ import annotations
from enum import StrEnum

DE_EV_CHARGER_CATEGORY = "qt"


class DeEVChargerDPCode(StrEnum):
    """Vendor specific DPCodes of the dé EV charger."""

    X_ALARM = "x_alarm"  # {"t": "2025-06-30 19:36:40", "v": 400}
    X_CHARGE_CURRENT = "x_charge_current"
    X_CHARGE_HISTORY = "x_charge_history"  # {"t": ..., "s": "17:17", "e": "08:28", "d": 6708, "c": 176}
    X_CHARGE_MODE = "x_charge_mode"  # {"m": 0, "dt": 0, "ss": "00:00", "se": "08:00"}
    X_CHARGER_INFO = "x_charger_info"  # {"r": ..., "fv": "1.0.2", "cp": "12.8", "t": "340", "e": "10595"}
    X_DO_CHARGE = "x_do_charge"
    X_DO_REBOOT = "x_do_reboot"
    X_MAX_CURRENT_CFG = "x_max_current_cfg"
    X_METRICS = "x_metrics"  # {"L1": [V, A, kW], "L2": [...], "L3": [...], "t": ..., "p": ..., "d": ..., "e": ...}
    X_WORK_ST_DEBUG = "x_work_st_debug"
    X_WORK_STATE = "x_work_state"


# x_work_state (and x_alarm "v") codes, from the device data model
WORK_STATES: dict[int, str] = {
    100: "offline",
    101: "not_connected",
    200: "connected",
    201: "charge_complete",
    202: "waiting_scheduled",
    203: "waiting_delayed",
    204: "paused",
    300: "charging",
    400: "overcurrent",
    401: "overvoltage",
    402: "undervoltage",
    403: "overtemperature",
    500: "selftest_failed",
    501: "residual_current",
    502: "relay_welded",
    503: "residual_current_selftest_failed",
    504: "cp_error",
    505: "other_error",
    506: "diode_failure",
    507: "earth_fault",
}
CHARGING_WORK_STATES: tuple[int, ...] = (300,)

CHARGE_MODES: dict[int, str] = {
    0: "immediate",
    1: "delayed",
    2: "scheduled",
}

WORK_ST_DEBUG_STATES: list[str] = [
    "sleep",
    "idle",
    "idleins",
    "working",
    "wait",
    "errorpause",
    "pause",
    "stop",
    "empty",
]
