"""Controllable-device quota tracking for OpenAPI (tuya_iot) hubs.

A Tuya free / Trial IoT-Core project can *monitor* 50 devices but only
*control* 10 distinct devices per calendar month — every device the project
sends a command to consumes one unit of that allowance, which refreshes on the
1st. Reads do not count. There is no Tuya endpoint that reports the current
usage, so we count it ourselves: whenever the integration successfully issues a
command through a hub's ``tuya_iot`` (OpenAPI) account, we record the target
device id in a per-hub, per-month set. The size of that set is the number of
controllable units used this month.

Commands issued from the SmartLife app go through Tuya's app cloud (a different
credential) and do not consume this project's allowance, so they are correctly
NOT counted here — only commands this integration sends via our OpenAPI keys.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

STORE_VERSION = 1
# Tuya Trial Edition cap. Kept here as a constant; bump if a hub is on a paid
# plan with a higher controllable allowance.
DEFAULT_CONTROLLABLE_LIMIT = 10


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _month_key(now: dt.datetime | None = None) -> str:
    now = now or _utcnow()
    return f"{now.year:04d}-{now.month:02d}"


def _next_reset(now: dt.datetime | None = None) -> str:
    now = now or _utcnow()
    year = now.year + (1 if now.month == 12 else 0)
    month = 1 if now.month == 12 else now.month + 1
    return f"{year:04d}-{month:02d}-01"


class ControllableQuotaTracker:
    """Per-hub monthly distinct-device counter for the OpenAPI controllable cap."""

    def __init__(
        self,
        hass: HomeAssistant,
        hub_id: str,
        limit: int = DEFAULT_CONTROLLABLE_LIMIT,
    ) -> None:
        self.hass = hass
        self.hub_id = hub_id
        self.limit = limit
        self._month = _month_key()
        self._devices: set[str] = set()
        self._store: Store = Store(hass, STORE_VERSION, f"xtend_tuya_quota_{hub_id}")
        self._listeners: list = []

    async def async_load(self) -> None:
        data = await self._store.async_load()
        if isinstance(data, dict) and data.get("month") == _month_key():
            self._month = data["month"]
            self._devices = set(data.get("devices", []))
        else:
            # Empty store or a stale month -> start the current month fresh.
            self._month = _month_key()
            self._devices = set()
            await self._async_save()

    async def _async_save(self) -> None:
        await self._store.async_save(
            {"month": self._month, "devices": sorted(self._devices)}
        )

    def _roll_month_if_needed(self) -> bool:
        cur = _month_key()
        if cur != self._month:
            self._month = cur
            self._devices = set()
            return True
        return False

    def record(self, device_id: str) -> None:
        """Record a successful OpenAPI command to ``device_id``.

        Thread-safe: called from the executor thread that runs send_commands.
        Persisting and notifying entities are bounced onto the event loop.
        """
        rolled = self._roll_month_if_needed()
        is_new = device_id not in self._devices
        if is_new:
            self._devices.add(device_id)
        if is_new or rolled:
            self.hass.add_job(self._async_save)
            self._notify_threadsafe()

    # ----- derived values (read on the event loop) -----

    @property
    def used(self) -> int:
        self._roll_month_if_needed()
        return len(self._devices)

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    @property
    def devices(self) -> list[str]:
        return sorted(self._devices)

    @property
    def reset_date(self) -> str:
        return _next_reset()

    # ----- listener plumbing for the sensor -----

    def add_listener(self, cb) -> None:
        self._listeners.append(cb)

    def remove_listener(self, cb) -> None:
        if cb in self._listeners:
            self._listeners.remove(cb)

    def _notify_threadsafe(self) -> None:
        for cb in list(self._listeners):
            self.hass.add_job(cb)


class XTControllableQuotaSensor(SensorEntity):
    """Hub-level sensor: distinct devices controlled via OpenAPI this month."""

    _attr_has_entity_name = False
    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(self, tracker: ControllableQuotaTracker, hub_label: str) -> None:
        self._tracker = tracker
        self._attr_unique_id = f"xt_controllable_quota_{tracker.hub_id}"
        self._attr_name = f"Controllable devices used ({hub_label})"
        self._attr_translation_key = "controllable_quota"

    async def async_added_to_hass(self) -> None:
        self._tracker.add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        self._tracker.remove_listener(self.async_write_ha_state)

    @property
    def native_value(self) -> int:
        return self._tracker.used

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "limit": self._tracker.limit,
            "remaining": self._tracker.remaining,
            "reset_date": self._tracker.reset_date,
            "devices": self._tracker.devices,
            "hub_id": self._tracker.hub_id,
        }
