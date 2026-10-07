"""Self-check for the QT-08W-T3 DP decoders (sensor.py).

Standalone (no HA import) — mirrors the byte math in the DPCodeSat0*/
DPCodeFlowStaVolume/DPCodeCounterCustom wrappers and asserts it against the
REAL payloads captured live 2026-07-15 (see irrigation-t3-dp-decode.md). Fails
if anyone shifts a byte offset. Run: `python test_t3_decode.py`.
"""
import base64


def battery(b):          # DPCodeSat0BatteryWrapper
    return b[3] & 0x7F if len(b) >= 4 else None


def next_run(b):         # DPCodeSat0NextRunWrapper
    if len(b) < 12:
        return None
    y, mo, d, h, mi = b[7], b[8], b[9], b[10], b[11]
    if y == 0xFF or mo == 0 or mo > 12 or d == 0 or d > 31:
        return None
    return f"20{y:02d}-{mo:02d}-{d:02d} {h:02d}:{mi:02d}:00"


# Same ceiling the wrapper uses; a reading above it is a DP glitch, not water.
SANE_CUR_CAP_MAX = 9000


def flow_volume(b):      # DPCodeFlowStaVolumeWrapper
    if len(b) < 5:
        return None
    vol = int.from_bytes(b[1:5], "big")
    if vol > SANE_CUR_CAP_MAX:
        return None      # glitch guard, same ceiling as cur_cap
    return vol


def counter_volume(csv):  # DPCodeCounterCustomVolumeWrapper
    p = csv.split(",")
    if len(p) < 5 or int(p[2]) == 65534:
        return None
    return int(p[3])


def time_task(b):  # DPCodeT3TimeTaskWrapper.update_data
    if len(b) < 12:
        return None
    mode, value = b[3], int.from_bytes(b[4:8], "big")
    hour, minute, days_mask, enabled = b[8], b[9], b[10], b[11]
    if not value and not hour and not minute and not days_mask and not enabled:
        return None  # empty slot
    return {"slot": b[1], "mode": "duration" if mode == 0 else "volume",
            "value": value, "hour": hour, "minute": minute,
            "days_mask": days_mask, "enabled": bool(enabled)}


def build_t3(index, mode, value, hour, minute, days_mask, enabled):
    # mirror of build_time_task_payload_t3 in timer_service.py
    return bytes([0, index, index, mode,
                  (value >> 24) & 0xFF, (value >> 16) & 0xFF,
                  (value >> 8) & 0xFF, value & 0xFF,
                  hour, minute, days_mask & 0x7F, 1 if enabled else 0])


def demo():
    d = base64.b64decode
    # sat_0 (701): battery 100%, next 2026-07-15 16:00
    sat = d("AAEAZAABABoHDxAAAA==")
    assert battery(sat) == 100, battery(sat)
    assert next_run(sat) == "2026-07-15 16:00:00", next_run(sat)
    # sat_0 charge-flag frame (byte3=0xE4) still = 100%
    assert battery(d("AAEA5AABABoHDg4tAA==")) == 100
    # sat_0 idle frame (ff schedule) -> no next run
    assert next_run(d("AAEAZAEBAP///////w==")) is None
    # flow_sta_0 (701): final frame volume 113 L
    assert flow_volume(d("AAAAAHEAAAJY//////////8A")) == 113
    # flow_sta_0 mid-run frame: 90 L
    assert flow_volume(d("AAAAAFoAAAAADhAAAA4QCgAA")) == 90
    # Glitch guard: the DP intermittently reports a physically impossible
    # total (the impeller tops out at 25 L/min, so 9000 L is already a 6 h
    # ceiling). Anything above it must be dropped, not shown as a run.
    assert flow_volume(bytes([0x00, 0x00, 0x02, 0xB5, 0xCA])) is None   # 177610 L
    assert flow_volume(bytes([0x00, 0x00, 0x00, 0x23, 0x28])) == 9000   # exactly at the ceiling, kept
    # counter_custom: last run 113 L; aborted (65534) -> None
    assert counter_volume("0,1,600,113,20260714161000") == 113
    assert counter_volume("0,1,65534,9,20260714155958") is None
    # time_task_0 — Timer A (idx0, 3min/180s, 03:03, Mon, duration)
    a = time_task(d("AAAAAAAAALQDAwEB"))
    assert a == {"slot": 0, "mode": "duration", "value": 180, "hour": 3,
                 "minute": 3, "days_mask": 0x01, "enabled": True}, a
    # Timer B (idx1, 6min/360s, 06:06, Tue, duration)
    b = time_task(d("AAEBAAAAAWgGBgIB"))
    assert b == {"slot": 1, "mode": "duration", "value": 360, "hour": 6,
                 "minute": 6, "days_mask": 0x02, "enabled": True}, b
    # Volume timer (idx1, 33 L, 05:07, all days)
    v = time_task(d("AAEBAQAAACEFB38B"))
    assert v["mode"] == "volume" and v["value"] == 33 and v["slot"] == 1, v
    # All-zero payload = empty slot
    assert time_task(bytes(12)) is None
    # builder round-trips through the decoder (write -> read parity)
    assert time_task(build_t3(1, 0, 360, 6, 6, 0x02, True)) == {
        "slot": 1, "mode": "duration", "value": 360, "hour": 6,
        "minute": 6, "days_mask": 0x02, "enabled": True}
    assert time_task(build_t3(2, 1, 33, 5, 7, 0x7F, True))["mode"] == "volume"
    # delete payload (all-zero at index) decodes as empty slot
    assert time_task(bytes([0, 3] + [0] * 10)) is None
    # cyc_control_0 single-run builder matches the live 706 capture
    assert cyc_control(60, 1) == bytes.fromhex("00000000003c01000001".zfill(20))
    assert cyc_control(60, 0)[9] == 0 and cyc_control(60, 1)[9] == 1
    print("T3 decode self-check OK")


def cyc_control(value, flag):  # mirror of build_cyc_control_payload
    return bytes([0, 0, (value >> 24) & 0xFF, (value >> 16) & 0xFF,
                  (value >> 8) & 0xFF, value & 0xFF, 1, 0, 0, flag & 0xFF])


if __name__ == "__main__":
    demo()
