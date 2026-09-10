"""Dual-write timer services for fdm5kw irrigation valve.

The device-side `time_task` DP executes locally and is offline-safe, but
empirical testing on 2026-05-12 against live hardware showed that
Tuya's cloud rewrites the device DP from the cloud timer registry ~10s
after a direct DP write. To make HA → SmartLife mutations durable we
write both: the DP for immediate local execution, then the cloud timer
registry (via OpenAPI) so the cloud doesn't roll back our change.

Cost: 1–2 OpenAPI calls per user-initiated timer mutation (set/delete).
Negligible compared to the historical periodic-poll regressions —
mutations are interactive, not on a timer.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any

from ...multi_manager.multi_manager import MultiManager
from ...multi_manager.shared.threading import XTEventLoopProtector
from ...util import get_all_multi_managers
from .const import (
    DAYS_OF_WEEK,
    TUYA_ERR_DEVICE_POOL_QUOTA,
    TUYA_ERR_DEVICE_POOL_QUOTA_MSG,
)

_LOGGER = logging.getLogger(__name__)

TIME_TASK_CODE = "time_task"
# QT-08W-T3 valves carry the indexed `time_task_0` DP instead of `time_task`,
# with a 12-byte payload (per-timer index at byte[1], not byte[0]). Same
# sliding-window model — only the DP code + byte layout differ, so the write
# path branches on device.status presence. See t3_valve_dp_decode memory.
TIME_TASK_CODE_T3 = "time_task_0"
MODE_DURATION = 0
MODE_VOLUME = 1

_QUOTA_NOTIFICATION_ID = "xtend_tuya_fdm5kw_cloud_quota"

# Circuit breaker — once the Tuya OpenAPI returns 60001001 ("controllable
# device pool quota insufficient") we stop hitting the cloud for N hours
# instead of burning calls that will all fail. The DP write path keeps
# running so timers still fire locally. Cleared on HA process restart or
# via `xtend_tuya.fdm5kw_clear_quota_lockout`. The quota is account-wide,
# so the lockout is module-global (one quota hit on any device blocks all
# cloud writes for every fdm5kw on the account).
QUOTA_LOCKOUT_SECONDS = 6 * 3600
_quota_lockout_until: float = 0.0


def _is_quota_locked_out() -> bool:
    return _quota_lockout_until > time.monotonic()


def _engage_quota_lockout() -> None:
    global _quota_lockout_until
    _quota_lockout_until = time.monotonic() + QUOTA_LOCKOUT_SECONDS
    _LOGGER.warning(
        "fdm5kw cloud-timer lockout engaged for %d s after Tuya quota error",
        QUOTA_LOCKOUT_SECONDS,
    )


def clear_quota_lockout() -> None:
    """Manual reset hook for the cloud-timer circuit breaker.

    Wired to `xtend_tuya.fdm5kw_clear_quota_lockout` service. Use after
    bumping the Tuya IoT-Core plan or freeing devices so the next user
    action retries the cloud write."""
    global _quota_lockout_until
    _quota_lockout_until = 0.0
    _LOGGER.warning("fdm5kw cloud-timer lockout cleared")


def _notify_quota_exceeded(hass) -> None:
    """Surface the controllable-device quota error as a persistent
    notification once per HA session. The cloud rejected the timer write
    but the device DP still saved locally, so we want the user to know
    *why* SmartLife/cloud sync is degraded without spamming the log on
    every subsequent write."""
    try:
        from homeassistant.components import persistent_notification

        persistent_notification.async_create(
            hass,
            TUYA_ERR_DEVICE_POOL_QUOTA_MSG,
            title="Tuya quota exceeded",
            notification_id=_QUOTA_NOTIFICATION_ID,
        )
    except Exception:
        _LOGGER.warning("Failed to emit persistent quota notification", exc_info=True)


def _handle_cloud_response(hass, op: str, device_id: str, resp: Any) -> None:
    """Inspect a Tuya OpenAPI response and surface known soft failures.
    Returns nothing; logging is the contract. Callers continue regardless
    so the DP write path stays best-effort."""
    if not isinstance(resp, dict):
        return
    code = resp.get("code")
    if code == TUYA_ERR_DEVICE_POOL_QUOTA:
        _LOGGER.warning(
            "Cloud %s for %s hit Tuya quota error %s — %s",
            op,
            device_id,
            code,
            TUYA_ERR_DEVICE_POOL_QUOTA_MSG,
        )
        _engage_quota_lockout()
        _notify_quota_exceeded(hass)


def _days_to_mask(days: list[str] | int | None) -> int:
    if days is None:
        return 0
    if isinstance(days, int):
        return days & 0x7F
    mask = 0
    for d in days:
        try:
            mask |= 1 << DAYS_OF_WEEK.index(d.capitalize())
        except ValueError:
            _LOGGER.warning("Unknown day %r (expected one of %s)", d, DAYS_OF_WEEK)
    return mask


def _mask_to_loops(mask: int) -> str:
    return "".join("1" if mask & (1 << i) else "0" for i in range(7))


def _mode_to_int(mode: str) -> int:
    if mode == "duration":
        return MODE_DURATION
    if mode == "volume":
        return MODE_VOLUME
    raise ValueError(f"mode must be 'duration' or 'volume', got {mode!r}")


def build_time_task_payload(
    slot: int,
    mode: int,
    value: int,
    hour: int,
    minute: int,
    days_mask: int,
    enabled: bool,
) -> str:
    """Build base64-encoded 11-byte time_task DP payload.

    Byte layout (verified 2026-06-05 against SmartLife app toggles):
    [slot, enabled, mode, value(4B BE), hour, minute, days_mask, const=1].
    byte[1] is the enable flag (1=active, 0=disabled) — SmartLife flips
    exactly this byte on toggle, keeping the rest of the payload. byte[10]
    is a constant 1 (NOT the enable flag, as the old spec assumed).
    """
    if not 0 <= slot <= 6:
        raise ValueError(f"slot must be 0–6, got {slot}")
    payload = bytes(
        [
            slot & 0xFF,
            1 if enabled else 0,
            mode & 0xFF,
            (value >> 24) & 0xFF,
            (value >> 16) & 0xFF,
            (value >> 8) & 0xFF,
            value & 0xFF,
            hour & 0xFF,
            minute & 0xFF,
            days_mask & 0x7F,
            1,
        ]
    )
    return base64.b64encode(payload).decode("ascii")


def build_delete_payload(slot: int) -> str:
    """Build base64 payload that clears a slot (count=0)."""
    if not 0 <= slot <= 6:
        raise ValueError(f"slot must be 0–6, got {slot}")
    return base64.b64encode(bytes([slot] + [0] * 10)).decode("ascii")


def build_time_task_payload_t3(
    index: int,
    mode: int,
    value: int,
    hour: int,
    minute: int,
    days_mask: int,
    enabled: bool,
) -> str:
    """Build base64 12-byte time_task_0 DP payload for QT-08W-T3.

    Byte layout (decoded live 2026-07-15, two duration timers on 706):
    [00, index, index, mode, value(4B BE), hour, minute, days_mask, enabled].
    byte[1] is the per-timer index (NOT byte[0] as on old valves); byte[2]
    mirrors the index in SmartLife's own writes; mode 0=duration(s)/1=vol(L),
    days bit0=Mon. A raw write of this shape applied on-device (48 s echo,
    cloud didn't roll back) — see t3_valve_dp_decode memory.
    """
    if not 0 <= index <= 6:
        raise ValueError(f"index must be 0–6, got {index}")
    payload = bytes(
        [
            0,
            index & 0xFF,
            index & 0xFF,
            mode & 0xFF,
            (value >> 24) & 0xFF,
            (value >> 16) & 0xFF,
            (value >> 8) & 0xFF,
            value & 0xFF,
            hour & 0xFF,
            minute & 0xFF,
            days_mask & 0x7F,
            1 if enabled else 0,
        ]
    )
    return base64.b64encode(payload).decode("ascii")


def build_delete_payload_t3(index: int) -> str:
    """Clear a T3 slot: all-zero 12-byte payload at the given index. index 0
    is the all-zeros frame confirmed to clear on 706 (2026-07-15)."""
    if not 0 <= index <= 6:
        raise ValueError(f"index must be 0–6, got {index}")
    return base64.b64encode(bytes([0, index] + [0] * 10)).decode("ascii")


def _is_t3(hass, device_id: str) -> bool:
    """T3 valve = carries the `time_task_0` DP. Detected from live status."""
    mm = _find_multi_manager(hass, device_id)
    if mm is None:
        return False
    device = mm.device_map.get(device_id)
    if device is None:
        return False
    return device.status.get(TIME_TASK_CODE_T3) is not None


def _find_multi_manager(hass, device_id: str) -> MultiManager | None:
    for mm in get_all_multi_managers(hass):
        if mm.device_map.get(device_id):
            return mm
    return None


def _find_iot_account(hass, device_id: str) -> Any:
    """Return the OpenAPI (tuya_iot) account for the device, or None."""
    for mm in get_all_multi_managers(hass):
        if mm.device_map.get(device_id):
            return mm.get_account_by_name("tuya_iot")
    return None


def _get_prior_slot(hass, device_id: str, slot: int) -> dict | None:
    """Look up the current slot data from the registry entity so we can
    match it against the cloud timer registry when deleting/overwriting.
    Returns None if the entity isn't loaded yet or the slot is empty."""
    # Local import avoids a circular import at module load time.
    from .sensor import DPCodeTimeTaskRegistryWrapper, Fdm5kwTimerRegistryEntity

    entity = Fdm5kwTimerRegistryEntity.INSTANCES.get(device_id)
    if entity is None:
        return None
    wrapper = entity._dpcode_wrapper
    if not isinstance(wrapper, DPCodeTimeTaskRegistryWrapper):
        return None
    return wrapper.slots.get(slot)


async def _write_time_task(
    multi_manager: MultiManager,
    device_id: str,
    b64_value: str,
    code: str = TIME_TASK_CODE,
) -> bool:
    commands = [{"code": code, "value": b64_value}]
    try:
        ok = await XTEventLoopProtector.execute_out_of_event_loop_and_return(
            multi_manager.send_commands, device_id, commands
        )
    except Exception:
        _LOGGER.exception("time_task DP write failed for %s", device_id)
        return False
    if not ok:
        _LOGGER.warning("time_task DP write rejected for %s", device_id)
        return False
    return True


def _ha_timezone(hass) -> tuple[str, str]:
    """Return (timezone_id, '+H:MM' utc offset) for HA's configured TZ."""
    from datetime import datetime
    try:
        import zoneinfo
    except ImportError:  # pragma: no cover
        from backports import zoneinfo  # type: ignore

    tz_name = getattr(hass.config, "time_zone", None) or "UTC"
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        tz = zoneinfo.ZoneInfo("UTC")
    offset = datetime.now(tz).utcoffset()
    if offset is None:
        return tz_name, "+0:00"
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    return tz_name, f"{sign}{total_minutes // 60}:{total_minutes % 60:02d}"


async def _post_cloud_timer(
    hass,
    account,
    device_id: str,
    hour: int,
    minute: int,
    days_mask: int,
    mode: int,
    value: int,
    enabled: bool,
    code: str = TIME_TASK_CODE,
) -> None:
    """Cloud timer create so the cloud doesn't roll back our DP write.
    Schema (verified 2026-05-12 against live hardware, fdm5kw category):
    - top-level: category, loops, timezone_id, time_zone, instruct
    - each instruct[]: time (HH:mm), functions [{code, value}]
    The GET response renders the same data with a different layout
    (timer rows nested under groups). Do NOT mirror the GET shape on POST.
    """
    if _is_quota_locked_out():
        _LOGGER.warning(
            "Cloud timer POST skipped for %s — quota lockout active (DP-only)",
            device_id,
        )
        return
    time_str = f"{hour:02d}:{minute:02d}"
    loops = _mask_to_loops(days_mask)
    start_time_sec = hour * 3600 + minute * 60
    # SmartLife's scheduler UI requires the rich `value` shape — verified
    # against a live account on 2026-05-12. A minimal body still
    # gets stored, but SL renders it as a half-broken "Single watering"
    # entry and its edit flow hangs.
    func_value = {
        "startTimeStr": time_str,
        "loops": loops,
        "duration": value if mode == MODE_DURATION else 0,
        "capacity": value if mode == MODE_VOLUME else 0,
        "startTime": start_time_sec,
        "start": True,
        "current": 0,
    }
    timezone_id, time_zone = _ha_timezone(hass)
    body = json.dumps(
        {
            "category": "timer",
            "loops": loops,
            "timezone_id": timezone_id,
            "time_zone": time_zone,
            "instruct": [
                {
                    "time": time_str,
                    "date": "00000000",
                    "functions": [{"code": code, "value": func_value}],
                }
            ],
        }
    )
    url = f"/v1.0/devices/{device_id}/timers"
    _LOGGER.warning(
        "Cloud timer POST -> %s body=%s account_type=%s",
        url,
        body,
        type(account).__name__,
    )
    try:
        resp = await XTEventLoopProtector.execute_out_of_event_loop_and_return(
            account.call_api, "POST", url, body
        )
    except Exception:
        _LOGGER.warning(
            "Cloud timer POST raised for %s (non-fatal)", device_id, exc_info=True
        )
        return
    _LOGGER.warning("Cloud timer POST response for %s: %s", device_id, resp)
    _handle_cloud_response(hass, "POST", device_id, resp)
    if not resp or not resp.get("success"):
        _LOGGER.warning(
            "Cloud timer POST returned no success for %s: %s", device_id, resp
        )


async def _delete_cloud_timer_by_match(
    hass, account, device_id: str, hour: int, minute: int, days_mask: int
) -> None:
    """List cloud timers, delete the one matching time+days. Best-effort."""
    if _is_quota_locked_out():
        _LOGGER.warning(
            "Cloud timer GET/DELETE skipped for %s — quota lockout active",
            device_id,
        )
        return
    list_url = f"/v1.0/devices/{device_id}/timers"
    _LOGGER.warning(
        "Cloud timer GET -> %s (match %02d:%02d mask=%d)",
        list_url,
        hour,
        minute,
        days_mask,
    )
    try:
        resp = await XTEventLoopProtector.execute_out_of_event_loop_and_return(
            account.call_api, "GET", list_url, None
        )
    except Exception:
        _LOGGER.warning(
            "Cloud timer list raised for %s (non-fatal)", device_id, exc_info=True
        )
        return
    _LOGGER.warning("Cloud timer GET response for %s: %s", device_id, resp)
    _handle_cloud_response(hass, "GET", device_id, resp)
    if not resp or not resp.get("success"):
        _LOGGER.warning(
            "Cloud timer GET non-success for %s, skipping delete", device_id
        )
        return
    time_str = f"{hour:02d}:{minute:02d}"
    loops = _mask_to_loops(days_mask)
    matched = False
    for category in resp.get("result", []):
        for group in category.get("groups", []):
            for timer in group.get("timers", []):
                # Prefer the top-level time/loops — always present, including
                # T3 app-created timers whose `functions` list comes back empty.
                funcs = timer.get("functions") or []
                v = funcs[0].get("value", {}) if funcs else {}
                t_time = timer.get("time") or v.get("startTimeStr")
                t_loops = timer.get("loops") or v.get("loops")
                if t_time == time_str and t_loops == loops:
                    # Tuya's selective timer delete takes the timer-group
                    # id as a *query-string* parameter; both path-style
                    # variants (/timers/{group_id}, /timer/group/{id}, …)
                    # return 1108 "uri path invalid". Verified against the
                    # live account on 2026-05-12 with a throwaway
                    # group: DELETE /timers?group_id=<gid> succeeds and
                    # only removes that group.
                    group_id = group.get("id")
                    if not group_id:
                        continue
                    matched = True
                    del_url = f"/v1.0/devices/{device_id}/timers?group_id={group_id}"
                    _LOGGER.warning("Cloud timer DELETE -> %s", del_url)
                    try:
                        del_resp = await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                            account.call_api, "DELETE", del_url, None
                        )
                        _LOGGER.warning(
                            "Cloud timer DELETE response for %s: %s",
                            device_id,
                            del_resp,
                        )
                        _handle_cloud_response(hass, "DELETE", device_id, del_resp)
                    except Exception:
                        _LOGGER.warning(
                            "Cloud timer DELETE raised for %s (non-fatal)",
                            device_id,
                            exc_info=True,
                        )
    if not matched:
        _LOGGER.warning(
            "Cloud timer no entries matched %s for %s", time_str, device_id
        )


async def set_timer(hass, data: dict) -> bool:
    device_id: str = data["device_id"]
    slot: int = int(data["slot"])
    hour: int = int(data["hour"])
    minute: int = int(data["minute"])
    mode: int = _mode_to_int(data.get("mode", "duration"))
    value: int = int(data["value"])
    days_mask: int = _days_to_mask(data.get("days"))
    enabled: bool = bool(data.get("enabled", True))

    multi_manager = _find_multi_manager(hass, device_id)
    if multi_manager is None:
        _LOGGER.error("No multi_manager found for device %s", device_id)
        return False

    # When this is an edit (not a create), look up the prior slot state so
    # we can delete the cloud entry that's about to be replaced. Avoids
    # duplicate SmartLife timer entries after time/day changes.
    prior = _get_prior_slot(hass, device_id, slot)

    # T3 valves carry the indexed 12-byte `time_task_0` DP; everything else
    # (cloud dual-write, prior-delete, disabled-skip) is identical — the cloud
    # POST just uses the `time_task_0` function code. Verified 2026-07-15:
    # POST /timers with code time_task_0 renders back on GET; DP write applies
    # and the cloud doesn't roll it back.
    is_t3 = _is_t3(hass, device_id)
    task_code = TIME_TASK_CODE_T3 if is_t3 else TIME_TASK_CODE
    if is_t3:
        b64 = build_time_task_payload_t3(
            slot, mode, value, hour, minute, days_mask, enabled
        )
    else:
        b64 = build_time_task_payload(
            slot, mode, value, hour, minute, days_mask, enabled
        )
    if not await _write_time_task(multi_manager, device_id, b64, code=task_code):
        return False

    account = _find_iot_account(hass, device_id)
    if account is None:
        _LOGGER.warning(
            "set_timer: no tuya_iot account for %s (DP write only, cloud may roll back)",
            device_id,
        )
        return True
    _LOGGER.warning(
        "set_timer: tuya_iot account found for %s (type=%s), proceeding to cloud write",
        device_id,
        type(account).__name__,
    )

    if prior is not None:
        _LOGGER.warning(
            "set_timer: prior slot %d for %s = %s, deleting cloud match first",
            slot,
            device_id,
            prior,
        )
        await _delete_cloud_timer_by_match(
            hass,
            account,
            device_id,
            int(prior.get("hour", hour)),
            int(prior.get("minute", minute)),
            int(prior.get("days_mask", days_mask)),
        )

    # Tuya's OpenAPI has no per-timer enable/disable toggle (PUT
    # /timers/groups/{gid}/status is rejected with 1108; PUT on the
    # group body ignores `status` and resets it to 1). The closest
    # equivalent: when HA marks the timer disabled, leave it out of
    # the cloud registry entirely so the cloud can't fire it. The
    # device DP still carries the disabled bit for offline execution.
    # Net effect in SmartLife: the entry disappears from the schedule
    # tab when disabled and reappears on re-enable. Verified
    # 2026-05-12.
    if not enabled:
        _LOGGER.warning(
            "set_timer: enabled=False for slot %d on %s — skipping cloud POST "
            "so SmartLife schedule doesn't fire (no API to keep a disabled entry)",
            slot,
            device_id,
        )
        return True

    await _post_cloud_timer(
        hass, account, device_id, hour, minute, days_mask, mode, value, enabled,
        code=task_code,
    )
    return True


async def _get_cloud_timer_keys(account, device_id: str) -> set[tuple[str, str]] | None:
    """GET the cloud timer registry and return the set of (time_str, loops)
    keys it holds. Read-only — draws the 26k/mo API-call pool, NOT the
    10-controllable-device cap. Returns None if the GET failed (so callers
    don't mistake an API failure for an empty cloud registry and wipe every
    HA slot as a ghost)."""
    list_url = f"/v1.0/devices/{device_id}/timers"
    try:
        resp = await XTEventLoopProtector.execute_out_of_event_loop_and_return(
            account.call_api, "GET", list_url, None
        )
    except Exception:
        _LOGGER.warning(
            "resync: cloud timer GET raised for %s (non-fatal)", device_id, exc_info=True
        )
        return None
    if not resp or not resp.get("success"):
        _LOGGER.warning("resync: cloud timer GET non-success for %s: %s", device_id, resp)
        return None
    keys: set[tuple[str, str]] = set()
    for category in resp.get("result", []):
        for group in category.get("groups", []):
            for timer in group.get("timers", []):
                # Top-level time/loops first — T3 app timers report empty
                # `functions`, so keying off the value dict alone would miss
                # them and (in resync) flag every enabled slot as an orphan.
                funcs = timer.get("functions") or []
                v = funcs[0].get("value", {}) if funcs else {}
                t = timer.get("time") or v.get("startTimeStr")
                loops = timer.get("loops") or v.get("loops")
                if t is not None and loops is not None:
                    keys.add((t, loops))
    return keys


async def resync_from_cloud(hass, data: dict) -> dict:
    """Reconcile the HA timer registry against the Tuya cloud, clearing the
    live orphan (zombie) slots the cloud no longer knows about.

    A *live orphan* = an ENABLED HA slot with no matching cloud timer. Enabled
    timers are always cloud-posted (`set_timer` posts on enable), so a missing
    cloud entry means the cloud rolled back / a SmartLife delete left the
    device slot live — it WILL water offline with no cloud entry (the 969
    04:20 case). Clear the device slot: a control write, 1 unit against the
    10/valve/month cap for this account.

    DISABLED slots are deliberately left alone. `set_timer` never posts a
    disabled timer to the cloud, so a legitimately user-disabled timer is
    indistinguishable from a disabled ghost by cloud state alone — dropping it
    would delete a real timer the user just toggled off. Disabled ghosts don't
    fire, so they're harmless clutter; leave manual cleanup for those.

    Read-first by construction: the GET is always free against the control
    cap; a write happens only per live orphan found. User-triggered per valve,
    so it can't runaway the quota the way a periodic sweep would."""
    device_id: str = data["device_id"]
    is_t3 = _is_t3(hass, device_id)

    account = _find_iot_account(hass, device_id)
    if account is None:
        _LOGGER.warning("resync: no tuya_iot account for %s — cannot reconcile", device_id)
        return {"success": False, "error": "no_cloud_account"}

    from .sensor import Fdm5kwTimerRegistryEntity

    entity = Fdm5kwTimerRegistryEntity.INSTANCES.get(device_id)
    if entity is None:
        _LOGGER.warning("resync: no timer registry entity loaded for %s", device_id)
        return {"success": False, "error": "no_registry_entity"}
    wrapper = entity._dpcode_wrapper
    slots: dict = getattr(wrapper, "slots", None)
    if slots is None:
        return {"success": False, "error": "no_registry_slots"}

    cloud_keys = await _get_cloud_timer_keys(account, device_id)
    if cloud_keys is None:
        return {"success": False, "error": "cloud_get_failed"}

    multi_manager = _find_multi_manager(hass, device_id)
    locked_out = _is_quota_locked_out()

    checked = orphans_cleared = orphans_deferred = 0
    for slot_idx, s in list(slots.items()):
        if not s:
            continue
        checked += 1
        # Only enabled slots are judged — disabled ones are never in the cloud
        # by design (see docstring), so "no cloud match" tells us nothing.
        if not s.get("enabled"):
            continue
        key = (
            f"{int(s.get('hour', 0)):02d}:{int(s.get('minute', 0)):02d}",
            _mask_to_loops(int(s.get("days_mask", 0))),
        )
        if key in cloud_keys:
            continue  # legit — cloud agrees it exists
        # Live orphan — fires offline with no cloud entry. Needs a device slot
        # clear (control write). Skip if quota-locked; the write would just
        # fail, so report it deferred rather than burn a call.
        if locked_out or multi_manager is None:
            orphans_deferred += 1
            _LOGGER.warning(
                "resync: live orphan slot %d on %s left in place (quota lockout / no manager)",
                slot_idx, device_id,
            )
            continue
        clear_payload = (
            build_delete_payload_t3(slot_idx) if is_t3
            else build_delete_payload(slot_idx)
        )
        clear_code = TIME_TASK_CODE_T3 if is_t3 else TIME_TASK_CODE
        if await _write_time_task(
            multi_manager, device_id, clear_payload, code=clear_code
        ):
            slots[slot_idx] = None
            orphans_cleared += 1
            _LOGGER.warning(
                "resync: cleared live orphan slot %d on %s (no cloud entry)",
                slot_idx, device_id,
            )
        else:
            orphans_deferred += 1

    if orphans_cleared:
        entity.async_write_ha_state()

    result = {
        "success": True,
        "checked": checked,
        "orphans_cleared": orphans_cleared,
        "orphans_deferred": orphans_deferred,
    }
    _LOGGER.warning("resync %s: %s", device_id, result)
    return result


async def delete_timer(hass, data: dict) -> bool:
    device_id: str = data["device_id"]
    slot: int = int(data["slot"])

    multi_manager = _find_multi_manager(hass, device_id)
    if multi_manager is None:
        _LOGGER.error("No multi_manager found for device %s", device_id)
        return False

    # Capture the slot's current time/days BEFORE we wipe the DP so we can
    # match the cloud timer entry on the way out.
    prior = _get_prior_slot(hass, device_id, slot)
    _LOGGER.warning(
        "delete_timer: device=%s slot=%d prior=%s", device_id, slot, prior
    )

    # T3 uses the indexed 12-byte clear + time_task_0 code; the cloud
    # delete-by-match below is code-agnostic (matches on time/loops).
    is_t3 = _is_t3(hass, device_id)
    if is_t3:
        b64 = build_delete_payload_t3(slot)
        task_code = TIME_TASK_CODE_T3
    else:
        b64 = build_delete_payload(slot)
        task_code = TIME_TASK_CODE
    if not await _write_time_task(multi_manager, device_id, b64, code=task_code):
        return False

    account = _find_iot_account(hass, device_id)
    if account is None:
        _LOGGER.warning(
            "delete_timer: no tuya_iot account for %s (DP-only delete)", device_id
        )
        return True
    if prior is None:
        _LOGGER.warning(
            "delete_timer: no prior slot data for %s slot %d — cannot match cloud entry",
            device_id,
            slot,
        )
        return True

    await _delete_cloud_timer_by_match(
        hass,
        account,
        device_id,
        int(prior.get("hour", 0)),
        int(prior.get("minute", 0)),
        int(prior.get("days_mask", 0)),
    )
    return True
