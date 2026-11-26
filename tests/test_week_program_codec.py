"""Self-check for week_program_codec.py (thermostat week_program_13_X DPs).

Standalone (no HA import). Payloads are real values from a Beok R7
thermostat (category "wk"). Run: `python tests/test_week_program_codec.py`
or with pytest.
"""

import importlib.util
import pathlib

_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components"
    / "xtend_tuya"
    / "week_program_codec.py"
)
_spec = importlib.util.spec_from_file_location("week_program_codec", _PATH)
codec = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(codec)

THURSDAY = "BAYAAMgIAACgCx4AoAweAKARAADNFgAAoA=="
MONDAY_FLAT = "AQYAAMgIAADICx4AyAweAMgRAADIFgAAyA=="


def test_decode_real_payload():
    day, periods = codec.decode(THURSDAY)
    assert day == 4
    assert periods == [
        (6, 0, 20.0),
        (8, 0, 16.0),
        (11, 30, 16.0),
        (12, 30, 16.0),
        (17, 0, 20.5),
        (22, 0, 16.0),
    ]


def test_to_text():
    assert (
        codec.to_text(THURSDAY)
        == "06:00 20.0, 08:00 16.0, 11:30 16.0, 12:30 16.0, 17:00 20.5, 22:00 16.0"
    )


def test_roundtrip():
    for raw in (THURSDAY, MONDAY_FLAT):
        day, _ = codec.decode(raw)
        assert codec.from_text(codec.to_text(raw), day) == raw


def test_lenient_input():
    text = "6:00=20; 08:00 20 ,11:30 20.0,12:30 20, 17:00 20 , 22:00 20"
    assert codec.from_text(text, 1) == MONDAY_FLAT


def test_rounds_to_half_degree():
    day, periods = codec.decode(
        codec.from_text("06:00 20.2, 08:00 20.3, 11:30 20, 12:30 20, 17:00 20, 22:00 20", 1)
    )
    assert periods[0][2] == 20.0 and periods[1][2] == 20.5


def _raises(text, day=1):
    try:
        codec.from_text(text, day)
    except codec.WeekProgramError:
        return True
    return False


def test_invalid_input():
    assert _raises("06:00 20, 08:00 20")  # wrong period count
    assert _raises("06:00 20, 05:00 20, 11:30 20, 12:30 20, 17:00 20, 22:00 20")  # order
    assert _raises("24:00 20, 08:00 20, 11:30 20, 12:30 20, 17:00 20, 23:00 20")  # hour
    assert _raises("06:00 2, 08:00 20, 11:30 20, 12:30 20, 17:00 20, 22:00 20")  # temp
    assert _raises("06:00 20, 08:00 20, 11:30 20, 12:30 20, 17:00 20, 22:00 20", 8)


def test_bad_raw_values():
    assert codec.decode(None) is None
    assert codec.decode("") is None
    assert codec.decode("not base64!") is None
    assert codec.decode("AQI=") is None  # too short


def test_day_from_dpcode():
    assert codec.day_from_dpcode("week_program_13_7") == 7
    assert codec.day_from_dpcode("week_program") is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("all ok")
