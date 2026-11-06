"""Self-check for TuyaOpenAPI.connect() reconnecting flag.

Standalone (no Home Assistant import): loads lib/tuya_iot/openapi.py by path,
with a stub logger in place of openlogging (which imports the HA-bound const).

The scenario that matters: connect() marks the token as "reconnecting", then the
login call raises (e.g. "[IOT API] connect_non_user_specific error"). If the
flag is not cleared, every later reconnect() waits in
`while self.token_info.is_reconnecting() is True` forever and the integration
hangs until Home Assistant restarts.

Run: `python tests/test_openapi_reconnecting.py` (needs `requests`)
"""

import importlib.util
import logging
import pathlib
import sys
import threading
import types

PKG_DIR = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components/xtend_tuya/lib/tuya_iot"
)
PKG = "xt_tuya_iot_under_test"

package = types.ModuleType(PKG)
package.__path__ = [str(PKG_DIR)]
sys.modules[PKG] = package
openlogging = types.ModuleType(f"{PKG}.openlogging")
openlogging.logger = logging.getLogger(PKG)  # type: ignore[attr-defined]
sys.modules[f"{PKG}.openlogging"] = openlogging

spec = importlib.util.spec_from_file_location(
    f"{PKG}.openapi", PKG_DIR / "openapi.py"
)
assert spec is not None and spec.loader is not None
openapi = importlib.util.module_from_spec(spec)
sys.modules[f"{PKG}.openapi"] = openapi
spec.loader.exec_module(openapi)


def make_api(fail_times):
    api = openapi.TuyaOpenAPI(
        "https://example.invalid",
        "id",
        "secret",
        shared_token_info=None,
        non_user_specific_api=True,
    )
    calls = {"n": 0}

    def fake_connect_non_user_specific():
        calls["n"] += 1
        if calls["n"] <= fail_times:
            raise Exception("[IOT API] connect_non_user_specific error")
        return {}

    api.connect_non_user_specific = fake_connect_non_user_specific
    return api, calls


def test_failed_connect_clears_reconnecting_flag():
    api, _ = make_api(fail_times=1)
    try:
        api.connect()
    except Exception:
        pass
    else:
        raise AssertionError("connect() should have raised")
    assert api.token_info.is_reconnecting() is False


def test_reconnect_after_failed_connect_does_not_hang():
    api, calls = make_api(fail_times=1)
    try:
        api.reconnect()
    except Exception:
        pass

    result = {}

    def second_reconnect():
        result["valid"] = api.reconnect()

    thread = threading.Thread(target=second_reconnect, daemon=True)
    thread.start()
    thread.join(timeout=2)
    assert not thread.is_alive(), "reconnect() is stuck waiting on the flag"
    assert calls["n"] == 2  # it actually retried the login
    assert result["valid"] is False


def test_successful_connect_clears_reconnecting_flag():
    api, _ = make_api(fail_times=0)
    assert api.connect() == {}
    assert api.token_info.is_reconnecting() is False


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok {name}")
