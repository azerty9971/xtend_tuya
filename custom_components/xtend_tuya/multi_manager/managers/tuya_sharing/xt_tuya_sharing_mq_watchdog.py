"""Watchdog for the Tuya Sharing MQ (MQTT push) client.

tuya_sharing.mq.SharingMQ renews its MQTT credentials every ~2 hours from its
own thread: it fetches a new MQ config over HTTP and replaces the paho client.
If that renewal never returns (for example an HTTP call without a timeout on a
half-open connection), nothing raises, nothing is logged and nothing retries.
The old client stops receiving pushes once its credentials lapse, so every
Tuya Sharing entity silently freezes until Home Assistant is restarted. In
override mode the same MQ client feeds the official Tuya integration too, so
both integrations freeze together.

This module only depends on the standard library so its logic can be tested
without Home Assistant (see tests/test_mq_watchdog.py).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

_LOGGER = logging.getLogger(__name__)

# tuya_sharing renews ~60 s before expireTime; the config usually says 7200 s.
DEFAULT_EXPIRE_TIME_S = 7200


class XTSharingMQHealth:
    """Decides whether a SharingMQ instance looks stalled.

    Feed it the currently active MQ object on every check. It returns a
    human-readable reason when the MQ is unhealthy, else None. All timing is
    relative to when this checker first saw a given MQ object / MQ config, so
    attaching to an already-running MQ can only delay a detection, never
    cause a false one.
    """

    def __init__(
        self,
        renewal_grace_s: float = 300,
        disconnect_grace_s: float = 300,
        startup_grace_s: float = 300,
    ) -> None:
        self.renewal_grace_s = renewal_grace_s
        self.disconnect_grace_s = disconnect_grace_s
        self.startup_grace_s = startup_grace_s
        self.reset()

    def reset(self) -> None:
        self._mq: Any = None
        self._mq_since: float = 0.0
        self._config: Any = None
        self._config_since: float = 0.0
        self._disconnected_since: float | None = None

    def check(self, mq: Any, now: float) -> str | None:
        if mq is None:
            self.reset()
            return None

        if mq is not self._mq:
            self.reset()
            self._mq = mq
            self._mq_since = now
            self._config_since = now

        # Being shut down by its owner (unload, refresh_mq): not our business.
        stop_event = getattr(mq, "_stop_event", None)
        if stop_event is not None and stop_event.is_set():
            return None

        # Thread.ident is None until start(); a started thread that is no
        # longer alive will never renew or reconnect again.
        if getattr(mq, "ident", None) is not None and not mq.is_alive():
            return "the MQ thread has exited"

        config = getattr(mq, "mq_config", None)
        if config is None:
            waited = now - self._mq_since
            if waited > self.startup_grace_s:
                return f"no MQ credentials were obtained {int(waited)} s after start"
            return None

        # SharingMQ replaces mq_config with a new object on every renewal.
        if config is not self._config:
            if self._config is not None:
                _LOGGER.debug("Tuya Sharing MQ credentials renewed")
            self._config = config
            self._config_since = now

        expire_time = getattr(config, "expire_time", 0) or DEFAULT_EXPIRE_TIME_S
        config_age = now - self._config_since
        if config_age > expire_time + self.renewal_grace_s:
            return (
                f"the MQ credentials were not renewed for {int(config_age)} s "
                f"(they are valid for {int(expire_time)} s), the renewal is "
                "probably stuck"
            )

        if self._is_connected(getattr(mq, "client", None)):
            self._disconnected_since = None
        elif self._disconnected_since is None:
            self._disconnected_since = now
        elif now - self._disconnected_since > self.disconnect_grace_s:
            return (
                "the MQTT client has been disconnected for "
                f"{int(now - self._disconnected_since)} s"
            )
        return None

    @staticmethod
    def _is_connected(client: Any) -> bool:
        if client is None:
            return False
        try:
            return bool(client.is_connected())
        except Exception:
            return False


class XTSharingMQWatchdog(threading.Thread):
    """Periodically checks the active SharingMQ and restarts it when stalled.

    get_mq returns the MQ object currently in use (it changes on every
    refresh_mq), restart_mq replaces it (normally the manager's refresh_mq).
    Restarts are rate limited so a real cloud/network outage does not turn
    into a reconnect storm.
    """

    def __init__(
        self,
        get_mq: Callable[[], Any],
        restart_mq: Callable[[], None],
        interval_s: float = 60,
        min_restart_interval_s: float = 600,
        health: XTSharingMQHealth | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(name="xtend_tuya_sharing_mq_watchdog", daemon=True)
        self._get_mq = get_mq
        self._restart_mq = restart_mq
        self.interval_s = interval_s
        self.min_restart_interval_s = min_restart_interval_s
        self.health = health if health is not None else XTSharingMQHealth()
        self._clock = clock
        self._shutdown = threading.Event()
        self._last_restart: float | None = None

    def stop(self) -> None:
        self._shutdown.set()

    def run(self) -> None:
        while not self._shutdown.wait(self.interval_s):
            try:
                self.check_once()
            except Exception:
                _LOGGER.exception("Tuya Sharing MQ watchdog check failed")

    def check_once(self) -> bool:
        """Run one check; returns True when a restart was triggered."""
        now = self._clock()
        reason = self.health.check(self._get_mq(), now)
        if reason is None:
            return False
        if (
            self._last_restart is not None
            and now - self._last_restart < self.min_restart_interval_s
        ):
            return False
        if self._shutdown.is_set():
            return False
        _LOGGER.warning(
            "Tuya Sharing MQ looks stalled: %s; restarting the MQ client", reason
        )
        self._last_restart = now
        self.health.reset()
        self._restart_mq()
        return True
