"""Build + cache a device_id -> (home, room) map for fdm5kw valves.

A valve's home and room are not in any DP, nor in the SmartLife sharing
device payload, nor in the OpenAPI thing-model (`bind_space_id` there points
at the home, and the space tree is empty for these accounts). The room
grouping lives only in the Tuya OpenAPI *Home Management* API:

    /v1.0/users/{uid}/homes              -> home id + name
    /v1.0/homes/{home}/rooms             -> room id + name
    /v1.0/homes/{home}/rooms/{rid}/devices -> which devices are in the room

We fetch it per hub from that hub's `tuya_iot` OpenAPI client, cache the
result process-wide, and refresh on a slow timer. These are read-only GETs
that do NOT count against the 10-controllable-devices/month quota (only
commands do), and the data is near-static, so the cost is negligible.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from aiohttp import web
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.http import HomeAssistantView

from ...const import DOMAIN, MESSAGE_SOURCE_TUYA_IOT

_LOGGER = logging.getLogger(__name__)

# device_id -> {"home": str, "room": str}
LOCATION_MAP: dict[str, dict[str, str]] = {}

# multi_manager ids already put on a refresh timer (avoid stacking intervals
# and avoid every valve re-walking homes/rooms on startup).
_SCHEDULED: set[int] = set()

# Called (no args) after LOCATION_MAP changes, so entities can re-publish the
# new home/room attributes without this module importing the sensor module.
REFRESH_LISTENERS: list[Callable[[], None]] = []

REFRESH_INTERVAL = timedelta(hours=12)

_VIEW_REGISTERED_KEY = f"{DOMAIN}_valve_locations_view"


def _iot_api(multi_manager: Any) -> Any | None:
    """Return the hub's OpenAPI client, or None if it has no tuya_iot account."""
    account = multi_manager.accounts.get(MESSAGE_SOURCE_TUYA_IOT)
    if account is None or getattr(account, "iot_account", None) is None:
        return None
    device_manager = account.iot_account.device_manager
    api = getattr(device_manager, "api", None)
    if api is None or getattr(api, "token_info", None) is None:
        return None
    return api


def _build_map(api: Any) -> dict[str, dict[str, str]]:
    """Blocking — walk homes -> rooms -> room devices for one hub."""
    result: dict[str, dict[str, str]] = {}
    uid = getattr(api.token_info, "uid", "") or ""
    if not uid:
        return result
    homes = api.get(f"/v1.0/users/{uid}/homes")
    if not isinstance(homes, dict) or not homes.get("success"):
        return result
    for home in homes.get("result") or []:
        home_id = home.get("home_id") or home.get("homeId")
        home_name = home.get("name") or ""
        if home_id is None:
            continue
        rooms = api.get(f"/v1.0/homes/{home_id}/rooms")
        rooms_result = rooms.get("result") or {}
        # /homes/{id}/rooms returns either {"rooms": [...]} or a bare list,
        # depending on DC/account; tolerate both.
        if isinstance(rooms_result, list):
            room_list = rooms_result
        else:
            room_list = rooms_result.get("rooms") or []
        for room in room_list:
            room_id = room.get("room_id")
            room_name = room.get("name") or ""
            if room_id is None:
                continue
            room_devices = api.get(f"/v1.0/homes/{home_id}/rooms/{room_id}/devices")
            for dev in room_devices.get("result") or []:
                device_id = dev.get("device_id") or dev.get("id") or dev.get("dev_id")
                if device_id:
                    result[device_id] = {"home": home_name, "room": room_name}
    return result


async def async_refresh(hass: HomeAssistant, multi_manager: Any) -> None:
    """Refresh the home/room map for one hub. Safe to call repeatedly."""
    api = _iot_api(multi_manager)
    if api is None:
        return
    try:
        mapping = await hass.async_add_executor_job(_build_map, api)
    except Exception:
        _LOGGER.debug("fdm5kw: valve home/room refresh failed", exc_info=True)
        return
    if mapping:
        LOCATION_MAP.update(mapping)
        _LOGGER.info(
            "fdm5kw: refreshed valve home/room for %d devices", len(mapping)
        )
        for listener in REFRESH_LISTENERS:
            try:
                listener()
            except Exception:
                _LOGGER.debug("fdm5kw: location refresh listener failed", exc_info=True)


async def async_ensure_scheduled(hass: HomeAssistant, multi_manager: Any) -> None:
    """Fill the map now and put this hub on a slow refresh timer.

    Guarded per hub: the first valve that lands here triggers one homes/rooms
    walk and arms the timer; later valves on the same hub are no-ops (they
    just read the already-filled LOCATION_MAP).
    """
    key = id(multi_manager)
    if key in _SCHEDULED:
        return
    _SCHEDULED.add(key)

    # One view registration across all hubs/entries (same pattern as the
    # calendar ICS view — the view reads the process-wide map at request time).
    if not hass.data.get(_VIEW_REGISTERED_KEY):
        hass.http.register_view(XTValveLocationsView())
        hass.data[_VIEW_REGISTERED_KEY] = True

    await async_refresh(hass, multi_manager)

    async def _tick(_now: Any) -> None:
        await async_refresh(hass, multi_manager)

    async_track_time_interval(hass, _tick, REFRESH_INTERVAL)


def get_location(device_id: str) -> dict[str, str] | None:
    """Return {'home', 'room'} for a device, or None if unknown."""
    return LOCATION_MAP.get(device_id)


class XTValveLocationsView(HomeAssistantView):
    """Serve LOCATION_MAP so the dashboard can group OFFLINE valves too.

    An unavailable registry sensor loses its valve_home/valve_room state
    attributes, so any grouping built from live states shows offline valves
    as "Unassigned" even though the cloud walk knows their room. This view
    is backed by the cloud data directly and is keyed by BOTH the Tuya
    device id and the HA device-registry id (the frontend only has the HA
    id for a valve whose registry sensor is unavailable).
    """

    url = f"/api/{DOMAIN}/valve_locations"
    name = f"api:{DOMAIN}:valve_locations"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        payload: dict[str, dict[str, str]] = dict(LOCATION_MAP)
        dev_reg = dr.async_get(hass)
        for tuya_id, loc in LOCATION_MAP.items():
            device = dev_reg.async_get_device(identifiers={(DOMAIN, tuya_id)})
            if device is not None:
                payload[device.id] = loc
        return self.json({"locations": payload})
