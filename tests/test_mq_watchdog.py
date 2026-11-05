"""Self-check for the Tuya Sharing MQ watchdog.

Standalone (no Home Assistant import): loads
multi_manager/managers/tuya_sharing/xt_tuya_sharing_mq_watchdog.py by path and
drives it with fake SharingMQ objects and a fake clock.

The scenario that matters is the silent stall: SharingMQ's 2-hourly
credential renewal never returns, so mq_config is never replaced, nothing is
logged, and the feed stays dead until Home Assistant restarts.

Run: `python tests/test_mq_watchdog.py`
"""

import importlib.util
import pathlib
import threading

MODULE = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components/xtend_tuya/multi_manager/managers/tuya_sharing"
    / "xt_tuya_sharing_mq_watchdog.py"
)
spec = importlib.util.spec_from_file_location("xt_mq_watchdog", MODULE)
wd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wd)

EXPIRE = 7200


class FakeConfig:
    def __init__(self, expire_time=EXPIRE):
        self.expire_time = expire_time


class FakeClient:
    def __init__(self, connected=True):
        self.connected = connected

    def is_connected(self):
        return self.connected


class FakeMQ:
    """Mimics the SharingMQ attributes the watchdog reads."""

    def __init__(self, started=True, alive=True):
        self._stop_event = threading.Event()
        self.ident = 1 if started else None
        self.alive = alive
        self.mq_config = FakeConfig()
        self.client = FakeClient()

    def is_alive(self):
        return self.alive

    def renew(self):
        self.mq_config = FakeConfig()
        self.client = FakeClient()


def run_for(health, mq, start, seconds, step=60, renew_every=None):
    """Advance the clock, return the first (time, reason) flagged, or None."""
    t = start
    while t <= start + seconds:
        if renew_every and t > start and (t - start) % renew_every == 0:
            mq.renew()
        reason = health.check(mq, t)
        if reason:
            return t, reason
        t += step
    return None


def test_healthy_mq_with_regular_renewals_is_never_flagged():
    mq = FakeMQ()
    # SharingMQ renews 60 s before expiry -> new config every 7140 s.
    assert run_for(wd.XTSharingMQHealth(), mq, 0, 10 * 3600, renew_every=7140) is None


def test_stuck_renewal_is_flagged_after_expiry_plus_grace():
    mq = FakeMQ()
    health = wd.XTSharingMQHealth(renewal_grace_s=300)
    flagged = run_for(health, mq, 0, 4 * 3600)
    assert flagged is not None
    t, reason = flagged
    assert EXPIRE + 300 < t <= EXPIRE + 300 + 60, t
    assert "not renewed" in reason, reason


def test_stuck_renewal_while_client_still_looks_connected():
    # The observed failure: no disconnect callback, client still "connected",
    # but no renewal. Must still be caught by the renewal check.
    mq = FakeMQ()
    mq.client = FakeClient(connected=True)
    assert run_for(wd.XTSharingMQHealth(), mq, 0, 3 * 3600) is not None


def test_dead_thread_is_flagged_immediately():
    mq = FakeMQ(alive=False)
    assert "exited" in wd.XTSharingMQHealth().check(mq, 0)


def test_not_started_thread_is_not_flagged():
    mq = FakeMQ(started=False, alive=False)
    mq.mq_config = None
    assert wd.XTSharingMQHealth().check(mq, 0) is None


def test_stopping_mq_is_ignored():
    mq = FakeMQ(alive=False)
    mq._stop_event.set()
    assert wd.XTSharingMQHealth().check(mq, 0) is None


def test_long_disconnect_is_flagged_short_one_is_not():
    mq = FakeMQ()
    health = wd.XTSharingMQHealth(disconnect_grace_s=300)
    assert health.check(mq, 0) is None
    mq.client.connected = False
    assert health.check(mq, 60) is None
    assert health.check(mq, 300) is None
    mq.client.connected = True  # recovered within the grace period
    assert health.check(mq, 330) is None
    mq.client = None
    assert health.check(mq, 400) is None
    assert "disconnected" in health.check(mq, 760)


def test_missing_config_after_startup_grace_is_flagged():
    mq = FakeMQ()
    mq.mq_config = None
    health = wd.XTSharingMQHealth(startup_grace_s=300)
    assert health.check(mq, 0) is None
    assert health.check(mq, 300) is None
    assert "no MQ credentials" in health.check(mq, 301)


def test_new_mq_object_resets_tracking():
    health = wd.XTSharingMQHealth()
    old = FakeMQ()
    assert health.check(old, 0) is None
    new = FakeMQ()
    # 2.5 h later the old one would be overdue, a fresh one is not.
    assert health.check(new, 9000) is None


def test_watchdog_restarts_and_rate_limits():
    clock = [0.0]
    current = {"mq": FakeMQ(alive=False)}
    restarts = []

    def restart():
        restarts.append(clock[0])
        current["mq"] = FakeMQ(alive=False)  # still broken after restart

    dog = wd.XTSharingMQWatchdog(
        get_mq=lambda: current["mq"],
        restart_mq=restart,
        min_restart_interval_s=600,
        clock=lambda: clock[0],
    )
    assert dog.check_once() is True
    clock[0] = 300
    assert dog.check_once() is False  # rate limited
    clock[0] = 601
    assert dog.check_once() is True
    assert restarts == [0.0, 601]


def test_watchdog_does_nothing_when_healthy_or_absent():
    calls = []
    dog = wd.XTSharingMQWatchdog(
        get_mq=lambda: None, restart_mq=lambda: calls.append(1), clock=lambda: 0
    )
    assert dog.check_once() is False
    mq = FakeMQ()
    dog = wd.XTSharingMQWatchdog(
        get_mq=lambda: mq, restart_mq=lambda: calls.append(1), clock=lambda: 0
    )
    assert dog.check_once() is False
    assert calls == []


def test_watchdog_thread_stops():
    dog = wd.XTSharingMQWatchdog(
        get_mq=lambda: None, restart_mq=lambda: None, interval_s=0.01
    )
    dog.start()
    dog.stop()
    dog.join(timeout=2)
    assert not dog.is_alive()


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} passed")


if __name__ == "__main__":
    main()
