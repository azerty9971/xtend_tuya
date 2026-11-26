"""Codec for Tuya thermostat week program raw DPs (week_program_13_1 .. _7).

Used by thermostats such as the Beok R7 (category "wk"). Each day is its own
raw DP, base64 encoded:

    byte 0           : day number (1..7, matches the DP suffix)
    then N x 4 bytes : hour, minute, temperature * 10 (uint16 big-endian)

Example (6 periods, 25 bytes):
    AQYAAMgIAADICx4AyAweAMgRAADIFgAAyA==
    01 | 06:00 20.0 | 08:00 20.0 | 11:30 20.0 | 12:30 20.0 | 17:00 20.0 | 22:00 20.0

The human readable form used by the text entity is:
    "06:00 20.0, 08:00 20.0, 11:30 20.0, 12:30 20.0, 17:00 20.0, 22:00 20.0"

This module has no Home Assistant dependency so it can be unit tested alone.
"""

from __future__ import annotations

import base64
import binascii
import re

DEFAULT_PERIOD_COUNT = 6
TEMP_MIN = 5.0
TEMP_MAX = 95.0

# Regex used by the text entity to validate user input in the UI
TEXT_PATTERN = (
    r"^\s*\d{1,2}:\d{2}\s*[ =]\s*\d{1,2}(\.\d)?"
    r"(\s*[,;]\s*\d{1,2}:\d{2}\s*[ =]\s*\d{1,2}(\.\d)?)*\s*$"
)

_PERIOD_RE = re.compile(r"(\d{1,2}):(\d{2})\s*[ =]\s*(\d{1,2}(?:\.\d)?)")


class WeekProgramError(ValueError):
    """Raised when a week program cannot be parsed or encoded."""


def decode(raw: str | None) -> tuple[int, list[tuple[int, int, float]]] | None:
    """Decode a base64 DP value into (day, [(hour, minute, temp), ...])."""
    if not raw:
        return None
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        return None
    if len(data) < 5 or (len(data) - 1) % 4 != 0:
        return None
    periods: list[tuple[int, int, float]] = []
    for i in range(1, len(data), 4):
        hour, minute = data[i], data[i + 1]
        temp = int.from_bytes(data[i + 2 : i + 4], "big") / 10
        periods.append((hour, minute, temp))
    return data[0], periods


def to_text(raw: str | None) -> str | None:
    """Base64 DP value -> "HH:MM T, HH:MM T, ..."."""
    if (decoded := decode(raw)) is None:
        return None
    _, periods = decoded
    return ", ".join(f"{h:02d}:{m:02d} {t:.1f}" for h, m, t in periods)


def from_text(
    text: str, day: int, period_count: int = DEFAULT_PERIOD_COUNT
) -> str:
    """"HH:MM T, ..." -> base64 DP value. Raises WeekProgramError."""
    if not 1 <= day <= 7:
        raise WeekProgramError(f"Invalid day {day}")
    matches = _PERIOD_RE.findall(text)
    if len(matches) != period_count:
        raise WeekProgramError(
            f"Expected {period_count} periods (HH:MM temperature), got {len(matches)}"
        )
    data = bytearray([day])
    previous = -1
    for hour_s, minute_s, temp_s in matches:
        hour, minute, temp = int(hour_s), int(minute_s), float(temp_s)
        if hour > 23 or minute > 59:
            raise WeekProgramError(f"Invalid time {hour_s}:{minute_s}")
        if hour * 60 + minute <= previous:
            raise WeekProgramError("Period times must be in ascending order")
        previous = hour * 60 + minute
        if not TEMP_MIN <= temp <= TEMP_MAX:
            raise WeekProgramError(
                f"Temperature {temp} out of range {TEMP_MIN}-{TEMP_MAX}"
            )
        # Thermostat uses 0.5 degree steps
        value = int(round(temp * 2)) * 5
        data += bytes([hour, minute]) + value.to_bytes(2, "big")
    return base64.b64encode(bytes(data)).decode()


def day_from_dpcode(dpcode: str) -> int | None:
    """week_program_13_3 -> 3."""
    suffix = dpcode.rsplit("_", 1)[-1]
    return int(suffix) if suffix.isdigit() else None
