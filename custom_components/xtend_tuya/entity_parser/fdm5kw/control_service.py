"""Single-watering (one_control) services for fdm5kw irrigation valve.

The one_control DP is a 6-byte payload:

    [mode, value(4 bytes uint32 BE), flag]

Modes:
    0 = idle (stops a running cycle)
    1 = duration  (value = seconds)
    3 = volume    (value = liters)

Byte 5 ("flag") is not yet fully understood; observed state writes use
zero, which matches what the device pushes back when idle. We use zero
for both writes; if the firmware needs a non-zero trigger we can revisit
once we have a captured packet from SmartLife in active mode.

This is the proper fix for the "duration ignored on second start" bug:
the existing valve switch + duration number entity decouples target from
trigger, so the device may use a stale value. Writing one_control directly
sends mode + value + start atomically.
"""

from __future__ import annotations

import base64
import logging

from ...multi_manager.multi_manager import MultiManager
from ...multi_manager.shared.threading import XTEventLoopProtector
from ...util import get_all_multi_managers

_LOGGER = logging.getLogger(__name__)

ONE_CONTROL_CODE = "one_control"
SWITCH_CODE = "switch"

# QT-08W-T3 valves have no `one_control` DP. Their manual single-run is the
# `cyc_control_0` DP, captured live 2026-07-15 (706 toggled on/off in SmartLife):
#     start = 00 00 00 00 00 3c 01 00 00 01   (value=60 s, flag byte[9]=1)
#     stop  = 00 00 00 00 00 3c 01 00 00 00   (flag byte[9]=0)
# Layout: [00, 00, value(4B BE), 01, 00, 00, flag]. byte[6]=01 = duration mode.
# The device runs `value` seconds then hardware-closes (counter_custom logged the
# actual run when stopped early), same offline-safe model as one_control.
CYC_CONTROL_CODE = "cyc_control_0"


def build_cyc_control_payload(value: int, flag: int) -> str:
    """Build base64 10-byte cyc_control_0 payload [00,00,value(4B BE),01,00,00,flag]."""
    if not 0 <= value <= 0xFFFFFFFF:
        raise ValueError(f"value out of range: {value}")
    payload = bytes(
        [
            0,
            0,
            (value >> 24) & 0xFF,
            (value >> 16) & 0xFF,
            (value >> 8) & 0xFF,
            value & 0xFF,
            1,
            0,
            0,
            flag & 0xFF,
        ]
    )
    return base64.b64encode(payload).decode("ascii")


def _is_t3(multi_manager: MultiManager, device_id: str) -> bool:
    """T3 valve = carries the `cyc_control_0` DP (no `one_control`)."""
    device = multi_manager.device_map.get(device_id)
    return device is not None and device.status.get(CYC_CONTROL_CODE) is not None

# one_control is a 6-byte payload: [lead, value(4-byte uint32 BE), flag].
#
# These leading-byte / flag values are NOT guesses — they were captured from
# the SmartLife app's own "single watering" command against FF East 10 (920)
# on 2026-06-08 via the Tuya device command log (event type 5):
#
#     one_control = AAAAAB4B  ->  bytes [0x00, 0x00,0x00,0x00,0x1E, 0x01]
#                                  lead=0  value=30 (seconds)  flag=1
#
# The device then ran exactly 30 s and auto-closed in hardware (cur_cap 0->17 L,
# switch reported false ~30 s later). So a single watering by duration is:
#   lead byte = 0  (NOT 1 — the old code's "duration mode = 1" was the bug;
#                   the firmware ignores lead=1, so the valve "didn't react",
#                   or cracked open via the flag with no armed timer -> no stop)
#   value     = duration in seconds
#   flag      = 1 (start) / 0 (idle/stop)
LEAD_SINGLE_RUN = 0
# Volume single-run has NOT been captured from SmartLife yet; this leading byte
# is an unverified guess kept only for the flow-meter fdm5kw. Valves without
# no flow meter and cannot hardware-stop by volume, so prefer duration.
LEAD_VOLUME = 3
FLAG_START = 1
FLAG_IDLE = 0


def build_one_control_payload(lead: int, value: int, flag: int) -> str:
    """Build base64-encoded 6-byte one_control DP payload [lead, value(4B BE), flag]."""
    if not 0 <= value <= 0xFFFFFFFF:
        raise ValueError(f"value out of range: {value}")
    payload = bytes(
        [
            lead & 0xFF,
            (value >> 24) & 0xFF,
            (value >> 16) & 0xFF,
            (value >> 8) & 0xFF,
            value & 0xFF,
            flag & 0xFF,
        ]
    )
    return base64.b64encode(payload).decode("ascii")


def _find_multi_manager(hass, device_id: str) -> MultiManager | None:
    for mm in get_all_multi_managers(hass):
        if mm.device_map.get(device_id):
            return mm
    return None


async def _send_commands(
    multi_manager: MultiManager, device_id: str, commands: list[dict]
) -> bool:
    try:
        ok = await XTEventLoopProtector.execute_out_of_event_loop_and_return(
            multi_manager.send_commands, device_id, commands
        )
    except Exception:
        _LOGGER.exception("DP write failed for %s: %s", device_id, commands)
        return False
    if not ok:
        _LOGGER.warning("DP write rejected for %s: %s", device_id, commands)
        return False
    return True


async def _write_one_control(
    multi_manager: MultiManager, device_id: str, b64_value: str
) -> bool:
    return await _send_commands(
        multi_manager, device_id, [{"code": ONE_CONTROL_CODE, "value": b64_value}]
    )


async def start_watering(hass, data: dict) -> bool:
    """Start a single watering cycle by duration (sec) or volume (L).

    Duration mode sends the exact ``one_control`` payload that SmartLife's own
    single-watering button sends (lead byte 0, value = seconds, flag = 1) — see
    the constant block above for the captured packet. The device runs the cycle
    and auto-closes in hardware after ``value`` seconds, independent of HA/cloud.
    This replaces the previous lead-byte-1 ("duration mode") payload, which the
    firmware did not recognise — the cause of the reported "mostly doesn't react / if
    it opens it never stops" report.

    Volume mode is still best-effort (lead byte unverified, flow-meter only).
    """
    device_id: str = data["device_id"]
    mode: str = data.get("mode", "duration")
    value: int = int(data["value"])
    if mode in ("idle", "stop"):
        raise ValueError("Use stop_watering for mode=idle/stop")
    if mode not in ("duration", "volume"):
        raise ValueError(f"mode must be 'duration' or 'volume', got {mode!r}")

    multi_manager = _find_multi_manager(hass, device_id)
    if multi_manager is None:
        _LOGGER.error("No multi_manager found for device %s", device_id)
        return False

    # T3: cyc_control_0 duration run (no one_control DP). Volume-mode cyclic run
    # not captured — duration only for now.
    if _is_t3(multi_manager, device_id):
        if mode == "volume":
            _LOGGER.warning(
                "start_watering: T3 %s volume mode unverified, running as duration",
                device_id,
            )
        b64 = build_cyc_control_payload(value, FLAG_START)
        return await _send_commands(
            multi_manager, device_id, [{"code": CYC_CONTROL_CODE, "value": b64}]
        )

    lead = LEAD_SINGLE_RUN if mode == "duration" else LEAD_VOLUME
    b64 = build_one_control_payload(lead, value, FLAG_START)
    return await _write_one_control(multi_manager, device_id, b64)


async def stop_watering(hass, data: dict) -> bool:
    """Stop an active watering cycle.

    Writes the SmartLife idle ``one_control`` frame (lead 0, value 0, flag 0) and
    also drops the ``switch`` DP as a belt-and-braces close. Either being a no-op
    on a given firmware is harmless.
    """
    device_id: str = data["device_id"]

    multi_manager = _find_multi_manager(hass, device_id)
    if multi_manager is None:
        _LOGGER.error("No multi_manager found for device %s", device_id)
        return False

    # T3: cyc_control_0 with flag byte[9]=0 stops the run.
    if _is_t3(multi_manager, device_id):
        return await _send_commands(
            multi_manager,
            device_id,
            [{"code": CYC_CONTROL_CODE, "value": build_cyc_control_payload(0, FLAG_IDLE)}],
        )

    ok = await _write_one_control(
        multi_manager,
        device_id,
        build_one_control_payload(LEAD_SINGLE_RUN, 0, FLAG_IDLE),
    )
    await _send_commands(multi_manager, device_id, [{"code": SWITCH_CODE, "value": False}])
    return ok
