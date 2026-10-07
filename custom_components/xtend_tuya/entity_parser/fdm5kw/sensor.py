"""Irrigation valve (fdm5kw) data parser for raw Tuya DP codes."""

from __future__ import annotations

import logging
import struct
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, ClassVar

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfVolume, UnitOfVolumeFlowRate
from homeassistant.helpers.event import async_track_time_interval
from tuya_device_handlers.definition.sensor import (
    SensorDefinition as TuyaSensorDefinition,
)

from ...const import XTDPCode
from ...ha_tuya_integration.tuya_integration_imports import (
    TuyaCustomerDevice,
    TuyaDPCodeRawWrapper,
    TuyaRawTypeInformation,
)
from ...multi_manager.multi_manager import (
    MultiManager,
    XTDevice,
)
from ...sensor import (
    XTSensorEntity,
    XTSensorEntityDescription,
)
from . import location_service

_LOGGER = logging.getLogger(__name__)

# DP codes not yet in XTDPCode — use string literals until PR is merged
DP_ONE_CONTROL = "one_control"
DP_TIME_TASK = "time_task"
DP_RUN_TASK_STA = "run_task_sta"
DP_CUR_CAP = "cur_cap"
DP_START_TIME = "start_time"

# Liters ceiling for one cur_cap reading (25 L/min impeller * 6 h cap). The
# cur_cap DP occasionally emits a garbage spike (e.g. 177610 L); a spike would
# otherwise produce an impossible derived flow burst (e.g. 260000 L/min).
SANE_CUR_CAP_MAX = 9000

# How often to re-publish the flow-rate sensor state while a run is active.
# Pure local recomputation (no API call) — cost is one recorder row per tick
# per running valve. 10s was chosen as the practical floor in testing.
FLOW_RATE_REFRESH = timedelta(seconds=10)

from .const import DAYS_OF_WEEK, DEVICE_CATEGORY

# ---------------------------------------------------------------------------
# Raw DP Wrappers
# ---------------------------------------------------------------------------


class XTDPCodeRawStatusWrapper(TuyaDPCodeRawWrapper):
    """Raw DP wrapper that also binds on status presence.

    tuya-device-handlers 0.0.22 changed ``DPCodeWrapper.find_dpcode`` to bind
    only when the DP is declared in the device *spec* (``device.function`` /
    ``device.status_range``) with ``type == RAW``. fdm5kw valves obtained over
    the sharing API report ``time_task`` / ``start_time`` / ``close_time`` /
    ``one_control`` as *status values* only — the sharing spec lists just DPs
    1 + 11 — so the strict lookup returns ``None`` and the timer/name/last-run
    entities silently vanish (regressed in the 0.0.22 merge, v4.4.181: ~85 of
    100 valves dropped to the bare "Valve" entity with no timer).

    Restore the pre-0.0.22 behaviour: try the spec-based lookup first (so
    OpenAPI-spec devices keep their real type information), and only if that
    misses, synthesize a ``RawTypeInformation`` from a DP that is present in
    ``device.status``. ``RawTypeInformation.read_device_value`` reads straight
    from ``device.status`` and base64-decodes — it never consults ``type_data``
    — so a synthesized instance decodes identically.
    """

    @classmethod
    def find_dpcode(
        cls,
        device: TuyaCustomerDevice,
        dpcodes: str | tuple[str, ...] | None,
        *,
        prefer_function: bool = False,
    ):
        if wrapper := super().find_dpcode(
            device, dpcodes, prefer_function=prefer_function
        ):
            return wrapper
        if dpcodes is None:
            return None
        if not isinstance(dpcodes, tuple):
            dpcodes = (dpcodes,)
        for dpcode in dpcodes:
            if device.status.get(dpcode) is not None:
                return cls(
                    dpcode=dpcode,
                    type_information=TuyaRawTypeInformation(
                        dpcode=dpcode, type_data="{}", report_type=None
                    ),
                )
        return None


class DPCodeTimestampWrapper(XTDPCodeRawStatusWrapper):
    """Decodes start_time / close_time: 6 bytes [year_offset, month, day, hour, minute, second]."""

    def read_device_status(self, device: TuyaCustomerDevice) -> str | None:
        if (decoded := super().read_device_status(device)) and len(decoded) == 6:
            y, mo, d, h, mi, s = struct.unpack("BBBBBB", decoded)
            # 0xFF bytes = no data / unset
            if y == 255 or mo == 0 or mo > 12 or d == 0 or d > 31:
                return None
            return f"20{y:02d}-{mo:02d}-{d:02d} {h:02d}:{mi:02d}:{s:02d}"
        return None


class DPCodeOneControlWrapper(XTDPCodeRawStatusWrapper):
    """Decodes one_control: 6 bytes [mode, param_hi, param_mid_hi, param_mid_lo, param_lo, ?]."""

    def __init__(self, dpcode: str, type_information: TuyaRawTypeInformation) -> None:
        super().__init__(dpcode, type_information)
        self.mode: int | None = None
        self.value: int | None = None

    def update_data(self, device: TuyaCustomerDevice) -> None:
        if (decoded := super().read_device_status(device)) and len(decoded) >= 6:
            self.mode = decoded[0]
            self.value = int.from_bytes(decoded[1:5], byteorder="big")


class DPCodeOneControlModeWrapper(DPCodeOneControlWrapper):
    """Returns the one_control *status* mode label.

    one_control status mirrors the last command payload [lead, value(4B BE), flag].
    Verified live 2026-06-09 by triggering single-waterings on 964 and reading status:
        idle (no single-watering):  [0,0,0,0,0,0]      value 0
        duration run/armed:         [0,0,0,V,V,1]      lead 0, value = seconds  (964=900, 977=10)
        volume run/armed:           [1,0,0,0,V,1]      lead 1, value = liters   (964 volume 5L → [1,0,0,0,5,1])
    So lead byte 0 = duration, 1 = volume — the same encoding as time_task's mode
    byte (0=duration, 1=volume). The pre-4.4.183 note in irrigation-dp-decoding.md
    (0=idle / 1=duration / 3=volume) was stale and is wrong on every count.

    A zero value means no single-watering is set -> "idle" (covers both a truly idle
    valve and a just-finished run, where the device clears the value but keeps the
    last lead byte). A non-zero value -> the lead byte gives the mode.
    """

    def read_device_status(self, device: TuyaCustomerDevice) -> str | None:
        self.update_data(device)
        if self.mode is None:
            return None
        if not self.value:
            return "idle"
        if self.mode == 0:
            return "duration"
        if self.mode == 1:
            return "volume"
        return f"unknown ({self.mode})"


class DPCodeOneControlValueWrapper(DPCodeOneControlWrapper):
    """Returns the one_control parameter value (duration in sec or volume in L)."""

    def read_device_status(self, device: TuyaCustomerDevice) -> int | None:
        self.update_data(device)
        return self.value


class DPCodeTimeTaskWrapper(XTDPCodeRawStatusWrapper):
    """Decodes time_task: 11 bytes.

    Layout (corrected 2026-06-05 against live SmartLife app toggles):
    [slot_index, enabled, mode, value(4 bytes uint32 BE), hour, minute,
     days_bitmask, const].
    - byte[1] = enable flag: 1=active, 0=disabled. SmartLife flips exactly
      this byte when you toggle a timer off/on; the rest of the payload is
      retained. (The old spec mislabelled this "count/always 1" — every
      sample then was active so byte[1] and byte[10] couldn't be told apart.)
    - byte[10] = constant 1 (NOT "enabled", as previously assumed).
    A true delete is byte[1]==0 with an all-zero payload; a merely disabled
    timer is byte[1]==0 with its real payload intact.

    The DP acts as a sliding window — only shows the last-written timer slot.
    The device stores all timers internally. Each edit pushes that slot's data.

    Mode: 0=duration (value in seconds), 1=volume (value in liters)
    Days bitmask: bit0=Mon, bit1=Tue, ..., bit6=Sun
    """

    def __init__(self, dpcode: str, type_information: TuyaRawTypeInformation) -> None:
        super().__init__(dpcode, type_information)
        self.slot_index: int = 0
        self.timer: dict | None = None

    def update_data(self, device: TuyaCustomerDevice) -> None:
        if decoded := super().read_device_status(device):
            if len(decoded) < 11:
                return
            self.slot_index = decoded[0]
            entry = decoded[2:11]
            # byte[1] is the enable flag (1=active, 0=disabled), NOT a count.
            # A true delete is byte[1]==0 AND an all-zero payload; a disabled
            # timer keeps its full payload with byte[1]==0 — keep it (greyed),
            # don't drop it (that was the "timer vanishes in HA" bug).
            enabled = decoded[1]
            if enabled == 0 and not any(entry):
                self.timer = None
                return
            mode = entry[0]
            value = int.from_bytes(entry[1:5], byteorder="big")
            hour = entry[5]
            minute = entry[6]
            days_mask = entry[7]
            # entry[8] == decoded[10] is a constant 1, not the enable flag.
            days = [
                DAYS_OF_WEEK[i] for i in range(7) if days_mask & (1 << i)
            ]
            self.timer = {
                "slot": self.slot_index,
                "hour": hour,
                "minute": minute,
                "mode": "duration" if mode == 0 else "volume",
                "value": value,
                "value_unit": "s" if mode == 0 else "L",
                "days": days,
                "days_mask": days_mask,
                "enabled": bool(enabled),
            }


class DPCodeTimeTaskSlotWrapper(DPCodeTimeTaskWrapper):
    """Returns the slot index of the last-modified timer."""

    def read_device_status(self, device: TuyaCustomerDevice) -> int | None:
        self.update_data(device)
        return self.slot_index if self.timer else None


class DPCodeTimeTaskSummaryWrapper(DPCodeTimeTaskWrapper):
    """Returns a human-readable summary of the last-modified timer."""

    def read_device_status(self, device: TuyaCustomerDevice) -> str | None:
        self.update_data(device)
        if not self.timer:
            return "No timer data"
        t = self.timer
        status = "ON" if t["enabled"] else "OFF"
        days_str = ",".join(t["days"]) if t["days"] else "none"
        if t["mode"] == "duration":
            duration_min = t["value"] // 60
            return (
                f"Slot {t['slot']}: {t['hour']:02d}:{t['minute']:02d} "
                f"{duration_min}min {days_str} [{status}]"
            )
        return (
            f"Slot {t['slot']}: {t['hour']:02d}:{t['minute']:02d} "
            f"{t['value']}L {days_str} [{status}]"
        )


class DPCodeTimeTaskRegistryWrapper(DPCodeTimeTaskWrapper):
    """Accumulates all 7 timer slots across DP updates.

    The device's time_task DP is a sliding window that only shows the
    last-written slot. This wrapper maintains a dict of all 7 slots,
    updating each slot as its data comes through the DP. The registry
    persists across HA restarts via the companion entity's state
    restoration. The device DP is the single source of truth — no cloud
    timer registry is consulted.
    """

    NUM_SLOTS = 7

    def __init__(self, dpcode: str, type_information: TuyaRawTypeInformation) -> None:
        super().__init__(dpcode, type_information)
        self.slots: dict[int, dict | None] = {i: None for i in range(self.NUM_SLOTS)}
        # The DP is a sliding window that shows the last write/delete. Apply
        # each unique payload to slots once; without this guard, every state
        # read would re-apply the last delete and wipe a previously restored
        # slot.
        self._last_applied_payload: bytes | None = None

    def read_device_status(self, device: TuyaCustomerDevice) -> str | None:
        """Parse DP, apply once per unique payload, return active count."""
        raw = super().read_device_status(device)
        payload = bytes(raw) if isinstance(raw, (bytes, bytearray)) else None
        if payload is not None and payload != self._last_applied_payload:
            self.update_data(device)
            if self.timer is not None:
                idx = self.timer["slot"]
                if 0 <= idx < self.NUM_SLOTS:
                    self.slots[idx] = dict(self.timer)
                    # Tuya's cloud registry can map two timers onto the same
                    # device slot (seen live on 969: 04:05 and 22:05 both as
                    # slot 1). When that slot's push carries a time+days that
                    # another slot already holds, the other entry is a stale
                    # duplicate of this same timer — drop it so the registry
                    # doesn't show one timer twice / a ghost that never fires.
                    for other, s in self.slots.items():
                        if (
                            other != idx
                            and s
                            and s.get("hour") == self.timer["hour"]
                            and s.get("minute") == self.timer["minute"]
                            and s.get("days_mask") == self.timer["days_mask"]
                        ):
                            _LOGGER.warning(
                                "time_task slot %d duplicates slot %d (%02d:%02d) — dropping stale entry",
                                other,
                                idx,
                                self.timer["hour"],
                                self.timer["minute"],
                            )
                            self.slots[other] = None
            elif self.slot_index is not None and 0 <= self.slot_index < self.NUM_SLOTS:
                # count=0 means slot was deleted
                self.slots[self.slot_index] = None
            self._last_applied_payload = payload
        active = sum(1 for s in self.slots.values() if s and s.get("enabled"))
        return str(active)

    def get_slots_dict(self) -> dict[str, dict | None]:
        """Return slots keyed by string index (for JSON-safe HA attributes)."""
        return {str(k): v for k, v in self.slots.items()}

    def restore_slots(self, data: dict) -> None:
        """Hydrate slots from HA state restoration."""
        for i in range(self.NUM_SLOTS):
            slot_data = data.get(str(i)) or data.get(i)
            if isinstance(slot_data, dict):
                self.slots[i] = slot_data
            else:
                self.slots[i] = None


# ---------------------------------------------------------------------------
# Custom Entity for Timer Registry
# ---------------------------------------------------------------------------


class Fdm5kwTimerRegistryEntity(XTSensorEntity):
    """Sensor that exposes all 7 timer slots as attributes.

    State value = count of active (enabled) timers.
    Attributes contain the full slot registry for the irrigation-timer-card.
    Slots accumulate from the device's time_task DP push events; the
    registry survives HA restarts via state restoration.
    """

    # device_id → live entity instance
    INSTANCES: ClassVar[dict[str, Fdm5kwTimerRegistryEntity]] = {}

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        wrapper = self._dpcode_wrapper
        if not isinstance(wrapper, DPCodeTimeTaskRegistryWrapper):
            return None
        slots = wrapper.get_slots_dict()
        active = sum(1 for s in slots.values() if s and s.get("enabled"))
        location = location_service.get_location(self.device.id) or {}
        return {
            "slots": slots,
            "active_count": active,
            "valve_name": self.device.name,
            "valve_home": location.get("home"),
            "valve_room": location.get("room"),
            "device_id": self.device.id,
            "product_name": getattr(self.device, "product_name", None),
        }

    async def async_added_to_hass(self) -> None:
        """Restore slot registry from previous HA state."""
        await super().async_added_to_hass()
        Fdm5kwTimerRegistryEntity.INSTANCES[self.device.id] = self

        # Populate the valve home/room map (and put the owning hub on a slow
        # refresh) the first time any timer sensor is added. Fire-and-forget:
        # a location fetch must never block or break entity setup.
        multi_manager = self.device.get_multi_manager(self.hass)
        if multi_manager is not None:
            self.hass.async_create_task(
                location_service.async_ensure_scheduled(self.hass, multi_manager)
            )

        wrapper = self._dpcode_wrapper
        if not isinstance(wrapper, DPCodeTimeTaskRegistryWrapper):
            return

        # Prime the idempotency guard with the device's current DP payload
        # before restoring slots; otherwise the next state read would re-apply
        # the last DP push (often a delete) and trample the restored data.
        try:
            wrapper.read_device_status(self.device)
        except Exception:
            _LOGGER.debug(
                "fdm5kw: priming read_device_status for %s failed",
                self.entity_id,
                exc_info=True,
            )

        last_state = await self.async_get_last_state()
        if last_state is not None:
            slots_data = last_state.attributes.get("slots")
            if isinstance(slots_data, dict):
                wrapper.restore_slots(slots_data)
                _LOGGER.debug(
                    "Restored timer registry for %s: %s",
                    self.entity_id,
                    slots_data,
                )

        # Force a state write so attributes (valve_name, slots, etc.) reach
        # the frontend immediately. Without this, devices that haven't seen
        # a fresh DP push since boot keep the prior boot's attributes — the
        # dashboard strategy then falls back to device_id for the tile name.
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        Fdm5kwTimerRegistryEntity.INSTANCES.pop(self.device.id, None)
        await super().async_will_remove_from_hass()


def _republish_valve_location() -> None:
    """Re-publish timer-registry state so newly-fetched home/room attributes
    reach the frontend immediately (the map fills async, after the entities'
    first state write). Runs in the event loop via location_service."""
    for entity in list(Fdm5kwTimerRegistryEntity.INSTANCES.values()):
        if entity.hass is not None:
            entity.async_write_ha_state()


if _republish_valve_location not in location_service.REFRESH_LISTENERS:
    location_service.REFRESH_LISTENERS.append(_republish_valve_location)


# ---------------------------------------------------------------------------
# Custom Entity for Derived Flow Rate (l/min)
# ---------------------------------------------------------------------------


class Fdm5kwFlowRateEntity(XTSensorEntity):
    """Derived instantaneous flow-rate sensor (liters/minute).

    Uses a differential method: between two 10 s samples, flow rate is
    `(cur_cap_now - cur_cap_prev) * 60 / delta_seconds`. The FDM5KW has
    a real Hall-effect impeller inside the valve body (2–25 L/min range
    per the QOTO QT-08W spec), so `cur_cap` reflects actual liters and
    the resulting graph captures real flow variations — pressure dips,
    partial restrictions, etc.

    The 10 s tick is purely local: it reads `device.status["cur_cap"]`,
    which is kept fresh by the upstream MQTT push. No Tuya API calls
    are issued.

    Idle state (run_task_sta != 1) reports 0.0. Below ~2 L/min the
    impeller doesn't tick and `cur_cap` stalls, so the derived rate
    will read 0 even with water flowing — a hardware limit, not a bug.
    """

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._refresh_unsub: Callable[[], None] | None = None
        self._was_running: bool = False
        self._last_cur_cap: int | None = None
        # Monotonic, not wall clock: this timestamp is only ever used to
        # measure the elapsed seconds between two cur_cap samples. A DST
        # change or an NTP step would otherwise land straight in the
        # divisor and produce a nonsense flow-rate spike.
        self._last_ts: float | None = None
        self._current_flow: float = 0.0

    @property
    def native_unit_of_measurement(self) -> str:
        # Hard-coded as a property to defeat the base XTSensorEntity's
        # unit inheritance from the `cur_cap` Tuya DP data-model, which
        # carries a Chinese-localized "升 (L)" unit string. This sensor
        # is a derived rate; force "L/min" regardless of what the upstream
        # DP definition says.
        return str(UnitOfVolumeFlowRate.LITERS_PER_MINUTE)

    @property
    def device_class(self) -> str | None:
        # Same reason: prevent the base class from injecting
        # SensorDeviceClass.WATER which forces a volume unit.
        return None

    @property
    def native_value(self) -> float:
        return self._current_flow

    def _recompute(self) -> bool:
        """Update self._current_flow. Returns True if a state write
        should fire (state changed, or run is active and the recorder
        wants a fresh row)."""
        running = self.device.status.get(DP_RUN_TASK_STA) == 1
        cur_cap_raw = self.device.status.get(DP_CUR_CAP) or 0
        try:
            cur_cap = int(cur_cap_raw)
        except (TypeError, ValueError):
            cur_cap = 0
        now = time.monotonic()

        if not running:
            changed = self._was_running or self._current_flow != 0.0
            self._current_flow = 0.0
            self._last_cur_cap = None
            self._last_ts = None
            self._was_running = False
            return changed

        if cur_cap > SANE_CUR_CAP_MAX:
            # Glitch spike in the cur_cap DP — ignore this sample so the
            # derived rate doesn't show an impossible burst. Keep the last
            # baseline; the next real reading resumes a sane delta.
            return False

        if not self._was_running or self._last_ts is None or self._last_cur_cap is None:
            # Run just started: capture baseline, emit 0 once.
            self._last_cur_cap = cur_cap
            self._last_ts = now
            changed = self._current_flow != 0.0 or not self._was_running
            self._current_flow = 0.0
            self._was_running = True
            return changed

        delta_t = now - self._last_ts
        if delta_t <= 0:
            return False
        delta_cap = max(0, cur_cap - self._last_cur_cap)
        self._current_flow = round(delta_cap * 60.0 / delta_t, 2)
        self._last_cur_cap = cur_cap
        self._last_ts = now
        self._was_running = True
        # Always emit while running so the graph has dense rows.
        return True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._refresh_unsub = async_track_time_interval(
            self.hass, self._on_tick, FLOW_RATE_REFRESH
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._refresh_unsub is not None:
            self._refresh_unsub()
            self._refresh_unsub = None
        await super().async_will_remove_from_hass()

    async def _on_tick(self, _now: datetime) -> None:
        if self._recompute():
            self.async_write_ha_state()


# ---------------------------------------------------------------------------
# QT-08W-T3 valve — raw DP wrappers (product rjnqkjk1pct15ku2)
# ---------------------------------------------------------------------------
# The T3 is a DIFFERENT product from the QT-08W (o6dagifntoafakst): indexed DP
# model (switch_1, time_task_0, flow_sta_0, sat_0, counter_custom), no
# vbat_state / cur_cap / one_control. Battery is byte-packed inside sat_0.
# Decoders validated against live captures 2026-07-15 — see
# ~/Documents/work/irrigation-t3-dp-decode.md. All descriptors below are
# DP-presence-gated, so they only spawn on T3 devices and never touch the old
# QT-08W (which lacks these codes) — same coexistence model as every other
# fdm5kw descriptor.

DP_T3_SAT = "sat_0"
DP_T3_FLOW_STA = "flow_sta_0"
DP_T3_COUNTER = "counter_custom"


class DPCodeSat0BatteryWrapper(XTDPCodeRawStatusWrapper):
    """T3 battery %: sat_0 byte[3] low 7 bits (high bit = charge/sun flag).

    sat_0 = 00 01 00 [BB] 00 01 00 [Y M D H M] 00 (13 B). 706 read 0x64=100,
    matching SmartLife's 100%.
    """

    def read_device_status(self, device: TuyaCustomerDevice) -> str | None:
        decoded = super().read_device_status(device)
        if decoded and len(decoded) >= 4:
            # ponytail: a lone byte3=0x00 glitch was seen once (07-13); returns
            # 0% for that frame. Debounce here if it proves noisy in the field.
            return str(decoded[3] & 0x7F)
        return None


class DPCodeSat0NextRunWrapper(XTDPCodeRawStatusWrapper):
    """T3 next-irrigation time from sat_0 bytes[7..11] = [Y-2000, M, D, H, M].
    0xFF year / month 0 (idle frame `..ff ff ff ff ff`) = no schedule -> None."""

    def read_device_status(self, device: TuyaCustomerDevice) -> str | None:
        decoded = super().read_device_status(device)
        if decoded and len(decoded) >= 12:
            y, mo, d, h, mi = decoded[7], decoded[8], decoded[9], decoded[10], decoded[11]
            if y == 0xFF or mo == 0 or mo > 12 or d == 0 or d > 31:
                return None
            return f"20{y:02d}-{mo:02d}-{d:02d} {h:02d}:{mi:02d}:00"
        return None


class DPCodeFlowStaVolumeWrapper(XTDPCodeRawStatusWrapper):
    """T3 watering volume (L): flow_sta_0 bytes[1:5] BE. Live-cumulative during a
    run, holds the last run's final total when idle. Captured mid-run 07-14:
    climbed 80..113 L; final frame bytes[1:5]=00 00 00 71 = 113 L (=app 113 L).
    """

    def read_device_status(self, device: TuyaCustomerDevice) -> str | None:
        decoded = super().read_device_status(device)
        if decoded and len(decoded) >= 5:
            vol = int.from_bytes(decoded[1:5], "big")
            if vol > SANE_CUR_CAP_MAX:
                return None  # glitch guard, same ceiling as cur_cap
            return str(vol)
        return None


class DPCodeCounterCustomWrapper(XTDPCodeRawStatusWrapper):
    """T3 counter_custom — a plain CSV STRING (not base64), last completed run:
    'mode,flag,duration_s,volume_L,timestamp'. e.g. '0,1,600,113,20260714161000'.
    duration 65534 (0xFFFE) = aborted/interrupted sentinel."""

    def _parse(self, device: TuyaCustomerDevice) -> dict | None:
        raw = device.status.get(self.dpcode)
        if not isinstance(raw, str) or "," not in raw:
            return None
        parts = raw.split(",")
        if len(parts) < 5:
            return None
        try:
            return {"duration": int(parts[2]), "volume": int(parts[3]), "ts": parts[4]}
        except ValueError:
            return None


class DPCodeCounterCustomVolumeWrapper(DPCodeCounterCustomWrapper):
    """Last completed-run volume (L). Skips the 0xFFFE aborted sentinel."""

    def read_device_status(self, device: TuyaCustomerDevice) -> str | None:
        p = self._parse(device)
        if not p or p["duration"] == 65534:
            return None
        return str(p["volume"])


DP_T3_TIME_TASK = "time_task_0"


class DPCodeT3TimeTaskWrapper(DPCodeTimeTaskWrapper):
    """T3 time_task_0 — 12 bytes, same sliding-window + per-timer-index model as
    the old valve, but a different layout (verified live 2026-07-15):
      [00, index, b2, mode, value(4B BE), hour, minute, days_mask, enabled]
    - byte[1] = per-timer index (the T3 equivalent of the old byte[0] slot) —
      PROVEN with two duration timers (A idx0, B idx1). NOT the enable flag.
    - byte[3] = mode (0=duration/seconds, 1=volume/liters).
    - byte[11] = enabled (1=active, 0=disabled).
    - byte[2] = a create/order marker (1 only on the create push), ignored.
    Ghost caveat (proven live): a SmartLife delete does NOT clear the DP or set
    enabled=0 — the device keeps re-reporting the stale timer. So, exactly like
    the old valve, deletions are invisible on the DP and need the reactive
    resync path; only an all-zero payload counts as an empty slot here.
    """

    def update_data(self, device: TuyaCustomerDevice) -> None:
        if decoded := super().read_device_status(device):
            if len(decoded) < 12:
                return
            self.slot_index = decoded[1]
            mode = decoded[3]
            value = int.from_bytes(decoded[4:8], byteorder="big")
            hour = decoded[8]
            minute = decoded[9]
            days_mask = decoded[10]
            enabled = decoded[11]
            # Empty/cleared slot = an all-zero payload (what a slot clear writes).
            if not value and not hour and not minute and not days_mask and not enabled:
                self.timer = None
                return
            days = [DAYS_OF_WEEK[i] for i in range(7) if days_mask & (1 << i)]
            self.timer = {
                "slot": self.slot_index,
                "hour": hour,
                "minute": minute,
                "mode": "duration" if mode == 0 else "volume",
                "value": value,
                "value_unit": "s" if mode == 0 else "L",
                "days": days,
                "days_mask": days_mask,
                "enabled": bool(enabled),
            }


# The Slot/Summary/Registry variants reuse the old read/accumulate logic and
# only swap in the T3 decoder via MRO (T3 update_data resolves before the base).
class DPCodeT3TimeTaskSlotWrapper(DPCodeTimeTaskSlotWrapper, DPCodeT3TimeTaskWrapper):
    pass


class DPCodeT3TimeTaskSummaryWrapper(DPCodeTimeTaskSummaryWrapper, DPCodeT3TimeTaskWrapper):
    pass


class DPCodeT3TimeTaskRegistryWrapper(DPCodeTimeTaskRegistryWrapper, DPCodeT3TimeTaskWrapper):
    pass


# ---------------------------------------------------------------------------
# Entity Descriptors
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Fdm5kwSensorEntityDescription(XTSensorEntityDescription):
    """Describes fdm5kw irrigation valve sensor entity."""



@dataclass(frozen=True)
class Fdm5kwTimerRegistryDescription(Fdm5kwSensorEntityDescription):
    """Descriptor that returns a Fdm5kwTimerRegistryEntity instead of base XTSensorEntity."""

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSensorEntityDescription,
        definition: TuyaSensorDefinition,
        supported_descriptors: dict[str, tuple[XTSensorEntityDescription, ...]],
    ) -> Fdm5kwTimerRegistryEntity:
        return Fdm5kwTimerRegistryEntity(
            device=device,
            device_manager=device_manager,
            description=XTSensorEntityDescription(**description.__dict__),
            definition=definition,
            supported_descriptors=supported_descriptors,
        )


@dataclass(frozen=True)
class Fdm5kwFlowRateDescription(Fdm5kwSensorEntityDescription):
    """Descriptor that returns a Fdm5kwFlowRateEntity (derived l/min)."""

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSensorEntityDescription,
        definition: TuyaSensorDefinition,
        supported_descriptors: dict[str, tuple[XTSensorEntityDescription, ...]],
    ) -> Fdm5kwFlowRateEntity:
        return Fdm5kwFlowRateEntity(
            device=device,
            device_manager=device_manager,
            description=XTSensorEntityDescription(**description.__dict__),
            definition=definition,
            supported_descriptors=supported_descriptors,
        )


class Fdm5kwSensor:
    FDM5KW_SENSORS: ClassVar[dict[str, tuple[XTSensorEntityDescription, ...]]] = {}

    @staticmethod
    def initialize_sensor() -> None:
        sensors: list[Fdm5kwSensorEntityDescription] = [
            # --- Timestamps ---
            # translation_key is what the strategy + calendar use to map a
            # sibling entity to its role (start/end/mode/registry). Existing
            # entities created before 4.4.150 have null translation_key in
            # the entity registry; the strategy + calendar fall back to
            # entity-id suffix matching for those.
            # NOTE: every descriptor below sets ignore_other_dp_code_handler=True.
            # Three descriptors share dpcode=time_task and two share one_control,
            # so the first to register marks the DP "handled" and the rest would
            # be suppressed by _supports_description (entity.py). Worse, once any
            # of these entities orphans (e.g. a hub re-add / device-id churn),
            # register_current_entities_as_handled_dpcode marks the DP handled on
            # every boot, so the parser permanently suppresses re-creating them
            # (the "914 timer never shows" regression). The flag makes each
            # entity register regardless — same fix as the cur_cap flow_rate race.
            Fdm5kwSensorEntityDescription(
                key=f"{XTDPCode.START_TIME}_timestamp",
                dpcode=XTDPCode.START_TIME,
                translation_key="start_time",
                name="Last watering start",
                icon="mdi:clock-start",
                entity_registry_enabled_default=True,
                ignore_other_dp_code_handler=True,
                wrapper_class=(DPCodeTimestampWrapper,),
            ),
            Fdm5kwSensorEntityDescription(
                key=f"{XTDPCode.CLOSE_TIME}_timestamp",
                dpcode=XTDPCode.CLOSE_TIME,
                translation_key="close_time",
                name="Last watering end",
                icon="mdi:clock-end",
                entity_registry_enabled_default=True,
                ignore_other_dp_code_handler=True,
                wrapper_class=(DPCodeTimestampWrapper,),
            ),
            # --- One-shot control status ---
            Fdm5kwSensorEntityDescription(
                key=f"{DP_ONE_CONTROL}_mode",
                dpcode=DP_ONE_CONTROL,
                translation_key="watering_mode",
                name="Watering mode",
                icon="mdi:water-pump",
                entity_registry_enabled_default=True,
                ignore_other_dp_code_handler=True,
                wrapper_class=(DPCodeOneControlModeWrapper,),
            ),
            Fdm5kwSensorEntityDescription(
                key=f"{DP_ONE_CONTROL}_value",
                dpcode=DP_ONE_CONTROL,
                translation_key="watering_value",
                name="Watering value",
                icon="mdi:water",
                entity_registry_enabled_default=True,
                ignore_other_dp_code_handler=True,
                wrapper_class=(DPCodeOneControlValueWrapper,),
            ),
            # --- Timer schedule ---
            Fdm5kwSensorEntityDescription(
                key=f"{DP_TIME_TASK}_slot",
                dpcode=DP_TIME_TASK,
                translation_key="timer_slot",
                name="Timer slot",
                icon="mdi:timer-outline",
                entity_registry_enabled_default=True,
                ignore_other_dp_code_handler=True,
                wrapper_class=(DPCodeTimeTaskSlotWrapper,),
            ),
            Fdm5kwSensorEntityDescription(
                key=f"{DP_TIME_TASK}_summary",
                dpcode=DP_TIME_TASK,
                translation_key="timer_schedule",
                name="Timer schedule",
                icon="mdi:calendar-clock",
                entity_registry_enabled_default=True,
                ignore_other_dp_code_handler=True,
                wrapper_class=(DPCodeTimeTaskSummaryWrapper,),
            ),
            # --- Timer registry (accumulates all 7 slots) ---
            Fdm5kwTimerRegistryDescription(
                key=f"{DP_TIME_TASK}_registry",
                dpcode=DP_TIME_TASK,
                translation_key="irrigation_timer_registry",
                name="Irrigation timer registry",
                icon="mdi:timer-cog",
                entity_registry_enabled_default=True,
                ignore_other_dp_code_handler=True,
                wrapper_class=(DPCodeTimeTaskRegistryWrapper,),
            ),
            # --- Derived flow rate (l/min) for watering-history graph ---
            # ignore_other_dp_code_handler keeps the upstream cur_cap
            # `watering_volume` entity registering even though both
            # descriptors share dpcode=cur_cap. Without it, the first
            # descriptor to register claims the DP and the other entity
            # never spawns -> "Volume Unavailable" in the Last Watering
            # card after the v4.4.136 upgrade.
            Fdm5kwFlowRateDescription(
                key=f"{DP_CUR_CAP}_flow_rate",
                dpcode=DP_CUR_CAP,
                translation_key="watering_flow_rate",
                name="Watering flow rate",
                icon="mdi:water-percent",
                entity_registry_enabled_default=True,
                ignore_other_dp_code_handler=True,
            ),
            # --- QT-08W-T3 valve (product rjnqkjk1pct15ku2) ---
            # DP-presence-gated to T3; these codes are absent on the old QT-08W.
            Fdm5kwSensorEntityDescription(
                key=f"{DP_T3_SAT}_battery",
                dpcode=DP_T3_SAT,
                translation_key="battery",
                name="Battery level",
                device_class=SensorDeviceClass.BATTERY,
                native_unit_of_measurement=PERCENTAGE,
                state_class=SensorStateClass.MEASUREMENT,
                entity_registry_enabled_default=True,
                ignore_other_dp_code_handler=True,
                wrapper_class=(DPCodeSat0BatteryWrapper,),
            ),
            Fdm5kwSensorEntityDescription(
                key=f"{DP_T3_FLOW_STA}_volume",
                dpcode=DP_T3_FLOW_STA,
                translation_key="watering_volume",
                name="Watering volume",
                device_class=SensorDeviceClass.WATER,
                native_unit_of_measurement=UnitOfVolume.LITERS,
                icon="mdi:water",
                entity_registry_enabled_default=True,
                ignore_other_dp_code_handler=True,
                wrapper_class=(DPCodeFlowStaVolumeWrapper,),
            ),
            Fdm5kwSensorEntityDescription(
                key=f"{DP_T3_SAT}_next_run",
                dpcode=DP_T3_SAT,
                translation_key="next_watering",
                name="Next watering",
                icon="mdi:clock-outline",
                entity_registry_enabled_default=True,
                ignore_other_dp_code_handler=True,
                wrapper_class=(DPCodeSat0NextRunWrapper,),
            ),
            # T3 timers — same registry/slot/summary as the old valve, on
            # time_task_0 with the 12-byte decoder. Matching translation_keys so
            # the dashboard strategy + timer card treat T3 like the old valves.
            Fdm5kwSensorEntityDescription(
                key=f"{DP_T3_TIME_TASK}_slot",
                dpcode=DP_T3_TIME_TASK,
                translation_key="timer_slot",
                name="Timer slot",
                icon="mdi:timer-outline",
                entity_registry_enabled_default=True,
                ignore_other_dp_code_handler=True,
                wrapper_class=(DPCodeT3TimeTaskSlotWrapper,),
            ),
            Fdm5kwSensorEntityDescription(
                key=f"{DP_T3_TIME_TASK}_summary",
                dpcode=DP_T3_TIME_TASK,
                translation_key="timer_schedule",
                name="Timer schedule",
                icon="mdi:calendar-clock",
                entity_registry_enabled_default=True,
                ignore_other_dp_code_handler=True,
                wrapper_class=(DPCodeT3TimeTaskSummaryWrapper,),
            ),
            Fdm5kwTimerRegistryDescription(
                key=f"{DP_T3_TIME_TASK}_registry",
                dpcode=DP_T3_TIME_TASK,
                translation_key="irrigation_timer_registry",
                name="Irrigation timer registry",
                icon="mdi:timer-cog",
                entity_registry_enabled_default=True,
                ignore_other_dp_code_handler=True,
                wrapper_class=(DPCodeT3TimeTaskRegistryWrapper,),
            ),
        ]

        Fdm5kwSensor.FDM5KW_SENSORS = {
            DEVICE_CATEGORY: tuple(sensors),
        }

    @staticmethod
    def get_descriptors_to_merge() -> (
        dict[str, tuple[XTSensorEntityDescription, ...]] | None
    ):
        return Fdm5kwSensor.FDM5KW_SENSORS
