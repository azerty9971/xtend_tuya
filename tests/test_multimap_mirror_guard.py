"""Self-check: the cross-map device mirror never collapses a DP dict.

Standalone (no Home Assistant import) — mirrors XTDeviceMap.set_device_key_value
and XTDevice.__setattr__ in multi_manager/shared/shared_classes.py.

One device can exist as several XTDevice copies (one per source map and the
master map) that the mirror keeps in step: a write to any copy is replayed to
all others with the same id. The copies know different amounts about the
device: a sharing-account copy carries 2 DPs, an OpenAPI copy ~30. When the
poorer copy is (re)converted after the richer one is registered, the mirror
replays its 2-DP status/function/status_range/local_strategy onto the richer
copy and every entity built from it loses those DPs until the next reload.
The guard drops a mirrored write that would halve a DP dict; a richer copy
still upgrades a poorer one and ordinary status updates still mirror.

Run: `python3 tests/test_multimap_mirror_guard.py`
"""

MIN_SIZE = 4
DP_ATTRS = ("function", "status_range", "status", "local_strategy")
REGISTRY: list = []


def is_dp_collapse(old, new):
    """Mirror of XTDeviceMap.is_dp_collapse."""
    if not isinstance(old, dict) or not isinstance(new, dict):
        return False
    if len(old) < MIN_SIZE:
        return False
    return len(new) * 2 <= len(old)


class Device:
    def __init__(self, id, status):
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "status", status)

    def __setattr__(self, attr, value):  # mirror of XTDevice.__setattr__
        object.__setattr__(self, attr, value)
        for m in REGISTRY:
            m.set_device_key_value(self.id, attr, value)


class Map(dict):
    def set_device_key_value(self, device_id, key, value):  # mirror
        if device := self.get(device_id):
            if hasattr(device, key) and getattr(device, key) != value:
                if key in DP_ATTRS and is_dp_collapse(getattr(device, key), value):
                    return None
                setattr(device, key, value)


def dps(n):
    return {f"dp{i}": i for i in range(n)}


def demo():
    REGISTRY.clear()
    openapi = Map(v=Device("v", dps(32)))
    master = Map(v=openapi["v"])  # the master map points at the same object
    sharing = Map(v=Device("v", dps(2)))
    REGISTRY.extend([openapi, master, sharing])

    # The sharing copy is converted: its 2-DP status is written on its object.
    sharing["v"].status = dps(2)
    assert len(openapi["v"].status) == 32, "poorer copy degraded the full one"

    # The full copy still upgrades the poorer one (alignment at end of load).
    master["v"].status = dps(32)
    assert len(sharing["v"].status) == 32

    # A normal in-place status change (values, same keys) still mirrors.
    openapi["v"].status = {**dps(32), "dp0": 99}
    assert sharing["v"].status["dp0"] == 99

    # Small dicts (below MIN_SIZE) are never treated as a collapse.
    a, b = Map(w=Device("w", dps(3))), Map(w=Device("w", dps(1)))
    REGISTRY[:] = [a, b]
    b["w"].status = dps(1)
    assert len(a["w"].status) == 1

    # A modest shrink (less than half) still mirrors.
    REGISTRY[:] = [openapi, sharing]
    sharing["v"].status = dps(20)
    assert len(openapi["v"].status) == 20
    print("ok")


if __name__ == "__main__":
    demo()
