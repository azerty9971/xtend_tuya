"""Self-check for get_config_entry_runtime_data's shape handling.

Standalone (no Home Assistant import) — mirrors the attribute lookup in
util.get_config_entry_runtime_data and asserts it against the runtime_data
shapes the two integrations actually store.

The case that matters is CoreTuyaDeviceListener. Home Assistant core stores a
bare DeviceListener in the official Tuya entry's runtime_data, and that object
carries only `hass`, `_entry` and `manager` (verified against core 2026.7.4,
homeassistant/components/tuya/coordinator.py). A previous version of the lookup
additionally required `.listener` or `.device_listener` to be present, so it
returned None for every official Tuya entry and silently disabled override
detection across every install.

Run: `python tests/test_runtime_data_lookup.py`
"""


def lookup(runtime_data):
    """Mirror of util.get_config_entry_runtime_data's manager resolution."""
    if runtime_data is None:
        return None
    device_manager = None
    if hasattr(runtime_data, "device_manager"):
        device_manager = runtime_data.device_manager
    if hasattr(runtime_data, "manager"):
        device_manager = runtime_data.manager
    if device_manager is None:
        return None
    # (manager, listener) — the listener is the runtime_data object itself
    return (device_manager, runtime_data)


class CoreTuyaDeviceListener:
    """homeassistant.components.tuya.coordinator.DeviceListener, as of 2026.7.4."""

    def __init__(self, manager):
        self.hass = object()
        self._entry = object()
        self.manager = manager


class XtendRuntimeData:
    """xtend_tuya's own HomeAssistantXTData."""

    def __init__(self, manager, listener):
        self.manager = manager
        self.listener = listener


class HalfBuilt:
    """A config entry caught mid-setup: no manager yet."""

    def __init__(self):
        self.hass = object()


def main():
    manager = object()

    # The regression: the official Tuya shape must resolve.
    core = CoreTuyaDeviceListener(manager)
    assert not hasattr(core, "listener"), "core DeviceListener grew a .listener"
    assert not hasattr(core, "device_listener")
    got = lookup(core)
    assert got is not None, "official Tuya runtime_data must resolve — override detection depends on it"
    assert got[0] is manager
    assert got[1] is core, "listener must be the runtime_data object itself"

    # Our own shape still resolves.
    xt_listener = object()
    xt = XtendRuntimeData(manager, xt_listener)
    got = lookup(xt)
    assert got is not None and got[0] is manager

    # Genuinely unusable shapes still yield None rather than raising.
    assert lookup(None) is None
    assert lookup(HalfBuilt()) is None

    print("runtime-data lookup self-check OK")


if __name__ == "__main__":
    main()
