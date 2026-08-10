"""XTDevice.__deepcopy__ must not drag the whole device map into each copy.

Standalone: run with an env that has homeassistant installed:
  python tests/test_device_deepcopy.py
"""

import copy
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from custom_components.xtend_tuya.multi_manager.shared.shared_classes import (
        XTDevice,
        XTDeviceMap,
    )
except ImportError as exc:
    print(f"SKIP: needs an env with homeassistant installed ({exc})")
    sys.exit(0)


def make_device(i):
    d = XTDevice()
    d.id = f"bf{i:020x}"
    d.name = f"Valve {i}"
    d.status = {f"dp_{n}": n for n in range(20)}
    d.status_range = {
        f"dp_{n}": {"code": f"dp_{n}", "type": "Integer", "values": '{"min":0,"max":100}'}
        for n in range(20)
    }
    d.local_strategy = {
        n: {"status_code": f"dp_{n}", "config_item": {"valueDesc": "{}"}} for n in range(20)
    }
    return d


XTDeviceMap.clear_master_device_map()
devices = {d.id: d for d in (make_device(i) for i in range(240))}
dev_map = XTDeviceMap(devices)  # sets device_map on every member
first = next(iter(devices.values()))
first.original_device = make_device(9999)

assert first.device_map is dev_map

# 1. Copy is a data snapshot: live links dropped, data isolated.
cp = copy.deepcopy(first)
assert cp.device_map is None
assert cp.original_device is None
assert cp.status == first.status and cp.status is not first.status
assert cp.status_range is not first.status_range
cp.status["dp_0"] = 12345
assert first.status["dp_0"] == 0, "copy mutated the original"

# 2. Mutating the copy must not sync back through the multimap machinery.
cp.name = "renamed copy"
assert first.name == "Valve 0"

# 3. Speed: one copy must not scale with map size. 240-device map, one copy
#    well under 50ms (the naive version copied all 240 devices here).
t0 = time.perf_counter()
for d in list(devices.values())[:50]:
    copy.deepcopy(d)
t = time.perf_counter() - t0
assert t < 1.0, f"50 copies took {t:.2f}s — still dragging the map along"

print(f"ok: snapshot semantics + 50 copies in {t * 1000:.0f}ms")
