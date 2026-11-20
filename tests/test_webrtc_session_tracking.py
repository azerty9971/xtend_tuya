"""Self-check for the Tuya IOT WebRTC session lifecycle (LEZN-D12, videolock).

The device supports a single concurrent stream session, keyed by the cloud
config's moto_id. If the previous session is not released (HA restart, closed
browser tab, missed close event) the device silently ignores every new offer
and the frontend spins forever. The fixes pinned here:

- the original config (with its moto_id) is kept in
  ``open_device_sessions`` independently of the expiring ``sdp_exchange``
  cache, so a ``disconnect`` sent after the cache entry expired still carries
  the correct moto_id and is published to the correct topic;
- a stale open session is released automatically before a new offer;
- the answer wait has a timeout and reports an error to the frontend.

Needs Home Assistant (with the tuya requirements) installed.

Run: `python tests/test_webrtc_session_tracking.py`
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# xt_tuya_iot_manager must be imported before the webrtc manager:
# webrtc -> ipc_manager -> ipc_mq -> xt_tuya_iot_mq -> xt_tuya_iot_manager
# is a circular chain that only resolves with xt_tuya_iot_manager loaded first.
import custom_components.xtend_tuya.multi_manager.managers.tuya_iot.xt_tuya_iot_manager  # noqa: F401,E402
from homeassistant.components.camera.webrtc import (  # noqa: E402
    WebRTCError,
)
from custom_components.xtend_tuya.multi_manager.managers.tuya_iot.ipc.webrtc.xt_tuya_iot_webrtc_manager import (  # noqa: E402
    XTIOTWebRTCConfig,
    XTIOTWebRTCManager,
)
from custom_components.xtend_tuya.multi_manager.managers.tuya_iot.ipc.xt_tuya_iot_ipc_manager import (  # noqa: E402
    XTIOTIPCManager,
)
from custom_components.xtend_tuya.camera import (  # noqa: E402
    XTCameraEntity,
)
from custom_components.xtend_tuya.const import (  # noqa: E402
    XTWebRTCStreamQuality,
)

DEVICE_ID = "bfe574f3a3850ab4aff1hn"
SINK_TOPIC = "tuya/ipc/{device_id}/moto_id/out"


class FakeDevice:
    def __init__(self, device_id: str = DEVICE_ID) -> None:
        self.id = device_id
        self.name = "Test camera"


class FakeWatcher:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def report_message(
        self,
        dev_id,
        message,
        category,
        device=None,
        print_stack=False,
        category_parameter=None,
        method="debug",
    ) -> None:
        self.messages.append((method, message))

    def warnings(self) -> list[str]:
        return [msg for m, msg in self.messages if m == "warning"]


class FakeMultiManager:
    def __init__(self) -> None:
        self.device_watcher = FakeWatcher()
        self.device_map = {DEVICE_ID: FakeDevice()}


class FakePublishResult:
    def __init__(self, rc: int = 0) -> None:
        self.rc = rc

    def wait_for_publish(self, timeout: int) -> bool:
        return True


class FakeMQClient:
    def __init__(self, connected: bool = True, publish_rc: int = 0) -> None:
        self.connected = connected
        self.publish_rc = publish_rc
        self.published: list[tuple[str, str]] = []

    def is_connected(self) -> bool:
        return self.connected

    def publish(self, topic, payload, **kwargs):
        self.published.append((topic, payload))
        return FakePublishResult(self.publish_rc)


class FakeMQConfig:
    def __init__(self) -> None:
        self.username = "cloud_abc123"
        self.sink_topic = {"stream": SINK_TOPIC}


class FakeMQ:
    def __init__(self) -> None:
        self.mq_config = FakeMQConfig()
        self.client = FakeMQClient()


class FakeTokenInfo:
    def __init__(self, uid: str = "uid123") -> None:
        self.uid = uid


class FakeAPI:
    def __init__(self, result: dict = {}, success: bool = True) -> None:
        self.result = result
        self.success = success
        self.calls = 0
        self.urls: list[str] = []
        self.token_info = FakeTokenInfo()

    def get(self, url: str) -> dict:
        self.calls += 1
        self.urls.append(url)
        return {"success": self.success, "result": self.result}


class FakeIPCManager:
    def __init__(self, api: FakeAPI | None = None) -> None:
        self.multi_manager = FakeMultiManager()
        self.mq = FakeMQ()
        self.api = api if api is not None else FakeAPI()
        self.non_user_api = FakeAPI(success=False)

    def get_from(self) -> str:
        return "abc123"

    def publish_to_ipc_mqtt(self, topic: str, msg: str, device_id: str = "") -> None:
        self.mq.client.published.append((topic, msg))


def make_manager(api: FakeAPI | None = None) -> tuple[XTIOTWebRTCManager, FakeIPCManager]:
    ipc = FakeIPCManager(api=api)
    return XTIOTWebRTCManager(ipc), ipc


def make_config(manager: XTIOTWebRTCManager, moto_id: str) -> XTIOTWebRTCConfig:
    return XTIOTWebRTCConfig(manager, {"moto_id": moto_id, "auth": "auth-token"})


def last_published_message(ipc: FakeIPCManager) -> tuple[str, dict]:
    topic, payload = ipc.mq.client.published[-1]
    return topic, json.loads(payload)


def test_resolve_prefers_session_config_over_open_and_cloud():
    manager, ipc = make_manager(api=FakeAPI(result={"moto_id": "moto_cloud"}))
    manager._create_session_if_necessary("s1")
    manager.sdp_exchange["s1"].webrtc_config = make_config(manager, "moto_session")
    manager.open_device_sessions[DEVICE_ID] = ("s1", make_config(manager, "moto_open"))
    assert manager._resolve_session_config("s1", DEVICE_ID).get("moto_id") == "moto_session"


def test_resolve_falls_back_to_open_session_after_cache_expiry():
    manager, ipc = make_manager(api=FakeAPI(result={"moto_id": "moto_cloud"}))
    open_cfg = make_config(manager, "moto_open")
    manager.open_device_sessions[DEVICE_ID] = ("s1", open_cfg)
    manager.sdp_exchange.clear()  # the session cache entry expired
    assert manager._resolve_session_config("s1", DEVICE_ID) is open_cfg
    # a different session id must not resolve to the open session's config
    assert manager._resolve_session_config("s2", DEVICE_ID).get("moto_id") == "moto_cloud"


def test_close_session_after_cache_expiry_uses_original_moto_id():
    manager, ipc = make_manager()
    manager.open_device_sessions[DEVICE_ID] = ("s1", make_config(manager, "moto_orig"))
    manager.sdp_exchange.clear()  # viewing for >10 min expired the cache entry
    manager.on_webrtc_close_session("s1", FakeDevice())

    assert DEVICE_ID not in manager.open_device_sessions
    topic, data = last_published_message(ipc)
    header = data["data"]["header"]
    assert header["type"] == "disconnect"
    assert header["sessionid"] == "s1"
    assert header["moto_id"] == "moto_orig"
    assert topic == f"tuya/ipc/{DEVICE_ID}/moto_orig/out"


def test_close_unknown_session_warns_and_publishes_nothing():
    manager, ipc = make_manager(api=FakeAPI(success=False))
    manager.on_webrtc_close_session("s1", FakeDevice())
    assert ipc.mq.client.published == []
    assert manager.open_device_sessions == {}
    assert ipc.multi_manager.device_watcher.warnings()


def test_close_stale_session_releases_previous_session():
    manager, ipc = make_manager()
    manager.open_device_sessions[DEVICE_ID] = ("old", make_config(manager, "moto_old"))
    manager.close_stale_session(FakeDevice())

    assert DEVICE_ID not in manager.open_device_sessions
    topic, data = last_published_message(ipc)
    header = data["data"]["header"]
    assert header["type"] == "disconnect"
    assert header["sessionid"] == "old"
    assert header["moto_id"] == "moto_old"
    assert topic == f"tuya/ipc/{DEVICE_ID}/moto_old/out"


def test_close_stale_session_is_a_noop_when_nothing_is_open():
    manager, ipc = make_manager()
    manager.close_stale_session(FakeDevice())
    assert ipc.mq.client.published == []
    assert manager.open_device_sessions == {}


def test_new_offer_records_the_open_session_for_the_device():
    manager, ipc = make_manager()
    # Simulate the offer handler recording the newly opened session, replacing
    # a previous one that was never closed (HA restart / missed close event).
    # The real offer path calls close_stale_session BEFORE this assignment.
    manager.open_device_sessions[DEVICE_ID] = ("old", make_config(manager, "moto_old"))
    manager.open_device_sessions[DEVICE_ID] = ("new", make_config(manager, "moto_new"))
    # The user closes the "new" session: disconnect carries moto_new.
    manager.on_webrtc_close_session("new", FakeDevice())
    assert DEVICE_ID not in manager.open_device_sessions
    _, data = last_published_message(ipc)
    assert data["data"]["header"]["sessionid"] == "new"
    assert data["data"]["header"]["moto_id"] == "moto_new"
    # A late close of the overwritten "old" session must not drop "new"'s entry.
    manager.open_device_sessions[DEVICE_ID] = ("new", make_config(manager, "moto_new"))
    manager.on_webrtc_close_session("old", FakeDevice())
    assert manager.open_device_sessions[DEVICE_ID][0] == "new"


def test_wait_for_answer_times_out_with_an_error():
    manager, ipc = make_manager()
    manager._create_session_if_necessary("s1")
    captured: list = []
    asyncio.run(
        manager._wait_for_answer("s1", captured.append, DEVICE_ID, timeout=1)
    )
    assert len(captured) == 1
    assert isinstance(captured[0], WebRTCError)
    assert captured[0].code == "webrtc_answer_timeout"


def test_wait_for_answer_is_cancelled_when_answer_arrives():
    manager, ipc = make_manager()
    manager._create_session_if_necessary("s2")
    manager.set_sdp_answer("s2", {"sdp": "v=0\r\n"})
    assert manager.sdp_exchange["s2"].answer_received is True
    captured: list = []
    asyncio.run(
        manager._wait_for_answer("s2", captured.append, DEVICE_ID, timeout=5)
    )
    assert captured == []


def test_wait_for_answer_is_a_noop_for_a_missing_session():
    manager, ipc = make_manager()
    captured: list = []
    asyncio.run(
        manager._wait_for_answer("gone", captured.append, DEVICE_ID, timeout=1)
    )
    assert captured == []


def test_cloud_config_request_uses_user_scoped_url():
    # The cloud only issues webrtc configs on the user-scoped route
    # (/v1.0/users/{uid}/devices/{id}/webrtc-configs); the device-scoped
    # route answers 115029 "device not supports" (LEZN-D12).
    api = FakeAPI(result={"moto_id": "moto_cloud"})
    manager, _ipc = make_manager(api=api)
    config = manager._get_config_from_cloud(DEVICE_ID, None)
    assert config is not None
    assert api.urls == [f"/v1.0/users/uid123/devices/{DEVICE_ID}/webrtc-configs"]


def test_cloud_config_request_falls_back_to_device_url_without_uid():
    api = FakeAPI(result={"moto_id": "moto_cloud"})
    api.token_info.uid = ""
    manager, _ipc = make_manager(api=api)
    config = manager._get_config_from_cloud(DEVICE_ID, None)
    assert config is not None
    assert api.urls == [f"/v1.0/devices/{DEVICE_ID}/webrtc-configs"]


def test_ipc_publish_drops_and_warns_when_client_is_missing():
    ipc = XTIOTIPCManager.__new__(XTIOTIPCManager)
    ipc.multi_manager = FakeMultiManager()
    ipc.mq = FakeMQ()
    ipc.mq.client = None
    ipc.publish_to_ipc_mqtt("t", "{}")
    assert "MQTT" in " ".join(ipc.multi_manager.device_watcher.warnings())


def test_ipc_publish_drops_and_warns_when_not_connected():
    ipc = XTIOTIPCManager.__new__(XTIOTIPCManager)
    ipc.multi_manager = FakeMultiManager()
    ipc.mq = FakeMQ()
    ipc.mq.client = FakeMQClient(connected=False)
    ipc.publish_to_ipc_mqtt("t", "{}")
    assert ipc.mq.client.published == []
    assert ipc.multi_manager.device_watcher.warnings()


def test_ipc_publish_warns_on_failed_publish():
    ipc = XTIOTIPCManager.__new__(XTIOTIPCManager)
    ipc.multi_manager = FakeMultiManager()
    ipc.mq = FakeMQ()
    ipc.mq.client = FakeMQClient(publish_rc=2)
    ipc.publish_to_ipc_mqtt("t", "{}")
    assert ipc.multi_manager.device_watcher.warnings()


def test_ipc_publish_succeeds_silently():
    ipc = XTIOTIPCManager.__new__(XTIOTIPCManager)
    ipc.multi_manager = FakeMultiManager()
    ipc.mq = FakeMQ()
    ipc.publish_to_ipc_mqtt("t", "{}")
    assert ipc.mq.client.published == [("t", "{}")]
    assert ipc.multi_manager.device_watcher.warnings() == []


class FakeHass:
    @property
    def loop(self):
        return asyncio.get_event_loop()


class FakeProvider:
    """Stands in for a registered CameraWebRTCProvider (e.g. go2rtc)."""

    def __init__(self) -> None:
        self.offers: list[str] = []
        self.candidates: list[str] = []
        self.closes: list[str] = []

    async def async_handle_async_webrtc_offer(
        self, camera, offer_sdp: str, session_id: str, send_message
    ) -> None:
        self.offers.append(session_id)

    async def async_on_webrtc_candidate(self, session_id: str, candidate) -> None:
        self.candidates.append(session_id)

    def async_close_session(self, session_id: str) -> None:
        self.closes.append(session_id)


class FakeIOTManager:
    def __init__(self) -> None:
        self.offers: list[str] = []
        self.candidates: list[str] = []
        self.closes: list[str] = []

    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message, device, hass, quality
    ) -> None:
        self.offers.append(session_id)

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate, device
    ) -> None:
        self.candidates.append(session_id)

    def on_webrtc_close_session(self, session_id: str, device) -> None:
        self.closes.append(session_id)


class FakeStream:
    def __init__(
        self,
        source: str,
        outputs: list[str] | None = None,
        available: bool = True,
    ) -> None:
        self.source = source
        self._outputs = {name: object() for name in (outputs or [])}
        self.available = available
        self.updated_sources: list[str] = []

    def outputs(self):
        return self._outputs

    def update_source(self, new_source: str) -> None:
        self.source = new_source
        self.updated_sources.append(new_source)


_MISSING = object()


def make_entity(
    iot_manager: FakeIOTManager | None = _MISSING,  # type: ignore[assignment]
    provider: FakeProvider | None = _MISSING,  # type: ignore[assignment]
    webrtc_config=None,
) -> XTCameraEntity:
    if iot_manager is _MISSING:
        iot_manager = FakeIOTManager()
    if provider is _MISSING:
        provider = FakeProvider()
    entity = XTCameraEntity.__new__(XTCameraEntity)
    entity.iot_manager = iot_manager
    entity._webrtc_provider = provider
    entity.webrtc_configuration = webrtc_config
    entity._tuya_sessions = set()
    entity.stream = None
    entity._create_stream_lock = None
    entity._stream_refresh_unsub = None
    entity.wait_for_candidates = None
    entity.wait_for_candidates_session = None
    entity.wait_for_resolution = None
    entity.wait_for_resolution_session = None
    entity.has_multiple_streams = False
    entity.stream_quality = XTWebRTCStreamQuality.HIGH_QUALITY
    entity.device = FakeDevice()
    entity.device_manager = FakeMultiManager()
    entity._hass = FakeHass()
    return entity


def test_offer_without_tuya_config_is_delegated_to_provider():
    # A videolock has no Tuya WebRTC config; the frontend may still offer
    # WebRTC because a provider (go2rtc) claims the RTSP source. The offer
    # must reach the provider, not the Tuya manager.
    entity = make_entity(webrtc_config=None)
    asyncio.run(entity.async_handle_async_webrtc_offer("offer", "s1", None))
    assert entity._webrtc_provider.offers == ["s1"]
    assert entity.iot_manager.offers == []
    assert "s1" not in entity._tuya_sessions


def test_offer_with_tuya_config_uses_tuya_and_tracks_the_session():
    entity = make_entity(webrtc_config=object())
    asyncio.run(entity.async_handle_async_webrtc_offer("offer", "s1", None))
    assert entity.iot_manager.offers == ["s1"]
    assert entity._webrtc_provider.offers == []
    assert entity._tuya_sessions == {"s1"}


def test_candidates_are_routed_by_session_type():
    entity = make_entity(webrtc_config=object())
    entity._tuya_sessions.add("s1")
    asyncio.run(
        entity.async_on_webrtc_candidate("s1", object())
    )
    asyncio.run(
        entity.async_on_webrtc_candidate("s2", object())
    )
    assert entity.iot_manager.candidates == ["s1"]
    assert entity._webrtc_provider.candidates == ["s2"]


def test_close_tuya_session_closes_the_tuya_manager_only():
    entity = make_entity(webrtc_config=object())
    entity._tuya_sessions.add("s1")
    entity.close_webrtc_session("s1")
    assert entity.iot_manager.closes == ["s1"]
    assert entity._webrtc_provider.closes == []
    assert entity._tuya_sessions == set()


def test_close_provider_session_delegates_to_the_provider():
    # Sessions that were never started through the Tuya manager belong to the
    # registered provider and must be closed there (the old code swallowed
    # them when iot_manager was None).
    entity = make_entity(webrtc_config=object())
    entity.close_webrtc_session("s2")
    assert entity._webrtc_provider.closes == ["s2"]
    assert entity.iot_manager.closes == []

    entity_no_iot = make_entity(iot_manager=None, webrtc_config=None)
    entity_no_iot.close_webrtc_session("s3")
    assert entity_no_iot._webrtc_provider.closes == ["s3"]


def test_create_stream_forces_fresh_source_on_reconnect():
    # The stream exists but is idle (viewer reconnected after a pause); the
    # cached RTSPS token may be dead, so a fresh source is required.
    stream = FakeStream("rtsps://host/stale")
    entity = make_entity()
    entity.stream = stream
    sources = []

    async def fresh_source():
        sources.append("rtsps://host/fresh")
        return sources[-1]

    entity.stream_source = fresh_source
    result = asyncio.run(entity.async_create_stream())
    assert result is stream
    assert sources == ["rtsps://host/fresh"]
    assert stream.updated_sources == ["rtsps://host/fresh"]


def test_periodic_refresh_updates_unavailable_stream_with_viewers():
    stream = FakeStream("rtsps://host/stale", outputs=["hls"], available=False)
    entity = make_entity()
    entity.stream = stream
    sources = []

    async def fresh_source():
        sources.append("rtsps://host/fresh")
        return sources[-1]

    entity.stream_source = fresh_source
    asyncio.run(entity._refresh_stream_source())
    assert sources == ["rtsps://host/fresh"]
    assert stream.updated_sources == ["rtsps://host/fresh"]
    # the next tick must stay scheduled
    assert entity._stream_refresh_unsub is not None


def test_periodic_refresh_skips_a_healthy_stream():
    stream = FakeStream("rtsps://host/live", outputs=["hls"], available=True)
    entity = make_entity()
    entity.stream = stream
    sources = []

    async def fresh_source():
        sources.append("rtsps://host/fresh")
        return sources[-1]

    entity.stream_source = fresh_source
    asyncio.run(entity._refresh_stream_source())
    assert sources == []
    assert stream.updated_sources == []


def test_periodic_refresh_skips_an_idle_stream_without_viewers():
    stream = FakeStream("rtsps://host/stale", available=False)
    entity = make_entity()
    entity.stream = stream
    sources = []

    async def fresh_source():
        sources.append("rtsps://host/fresh")
        return sources[-1]

    entity.stream_source = fresh_source
    asyncio.run(entity._refresh_stream_source())
    assert sources == []
    assert stream.updated_sources == []


def test_refresh_is_a_noop_when_the_source_is_unchanged():
    stream = FakeStream("rtsps://host/same", outputs=["hls"], available=False)
    entity = make_entity()
    entity.stream = stream

    async def fresh_source():
        return "rtsps://host/same"

    entity.stream_source = fresh_source
    asyncio.run(entity._refresh_stream_source())
    assert stream.updated_sources == []


def test_remove_cancels_stream_refresh_timer():
    entity = make_entity()

    async def schedule():
        entity._schedule_stream_source_refresh()

    asyncio.run(schedule())
    unsub = entity._stream_refresh_unsub
    assert unsub is not None
    cancelled = []

    def tracking_cancel():
        cancelled.append(1)
        unsub()

    entity._stream_refresh_unsub = tracking_cancel
    asyncio.run(entity.async_will_remove_from_hass())
    assert cancelled == [1]
    assert entity._stream_refresh_unsub is None


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"{len(tests)} passed")


if __name__ == "__main__":
    main()
