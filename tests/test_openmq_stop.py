"""Self-check for TuyaOpenMQ.stop() racing the MQ thread.

Standalone (no Home Assistant import): loads lib/tuya_iot/openmq.py by path,
with a stub logger in place of openlogging (which imports the HA-bound const).

stop() holds _client_lock while paho's loop_stop() joins its network thread,
which can take up to a second. When the MQ thread's 1 s tick lands in that
window it waits on the lock, and once stop() releases it _run_mqtt() built and
loop_start()ed a new client that nobody ever stopped, so every config entry
reload leaked a paho thread and its sockets (#1075).

Run: `python tests/test_openmq_stop.py` (needs paho-mqtt, pycryptodome, requests)
"""

import importlib.util
import logging
import pathlib
import sys
import time
import types

PKG_DIR = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components/xtend_tuya/lib/tuya_iot"
)
PKG = "xt_tuya_iot_openmq_under_test"

package = types.ModuleType(PKG)
package.__path__ = [str(PKG_DIR)]
sys.modules[PKG] = package
openlogging = types.ModuleType(f"{PKG}.openlogging")
openlogging.logger = logging.getLogger(PKG)  # type: ignore[attr-defined]
sys.modules[f"{PKG}.openlogging"] = openlogging

spec = importlib.util.spec_from_file_location(f"{PKG}.openmq", PKG_DIR / "openmq.py")
assert spec is not None and spec.loader is not None
openmq = importlib.util.module_from_spec(spec)
sys.modules[f"{PKG}.openmq"] = openmq
spec.loader.exec_module(openmq)


class FakeClient:
    def is_connected(self):
        return True

    def loop_stop(self):
        pass

    def disconnect(self):
        pass


def test_run_mqtt_after_stop_does_not_start_a_client():
    mq = openmq.TuyaOpenMQ(api=None)  # type: ignore[arg-type]
    mq.mq_config = openmq.TuyaMQConfig(
        {
            "t": int(time.time() * 1000),
            "result": {"url": "ssl://example.invalid:8883", "expire_time": 7200},
        }
    )
    started = []

    def fake_start():
        started.append(FakeClient())
        return started[-1]

    mq._start = fake_start

    mq.stop()
    mq._run_mqtt()

    assert started == []
    assert mq.client is None


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} passed")


if __name__ == "__main__":
    main()
