from __future__ import annotations
from types import SimpleNamespace
from typing import Any
import json
from tuya_sharing.device import (
    CustomerDevice,
    DeviceRepository,
)
import custom_components.xtend_tuya.multi_manager.managers.tuya_sharing.xt_tuya_sharing_manager as sm
from .xt_tuya_sharing_api import (
    XTSharingAPI,
)
from ...multi_manager import (
    MultiManager,
)
from ...shared.shared_classes import (
    XTDeviceFunction,
    XTDeviceStatusRange,
)
from ...shared.threading import (
    XTThreadingManager,
)
from ....const import (
    LOGGER,  # noqa: F401
)

# Known DP layouts for device categories whose Tuya-side specifications/status
# are empty for some products (the cloud "shadow properties" data model exposes
# these dpcodes, but the legacy DP status/specification APIs never populated
# them for these products). Values mirror the well-documented layout used by
# the community "Tuya Local" workaround for the same hardware.
# See: https://github.com/home-assistant/core/issues/150902 (and duplicates
# #142137, #130949, #135280) plus
# https://community.home-assistant.io/t/tuya-t-h-sensor-unsupported/850996
_KNOWN_CATEGORY_DP_SPECS: dict[str, dict[str, dict[str, Any]]] = {
    # "tdq" here is the temperature & humidity sensor product line (product_id
    # x3o8epevyeo3z3oa "T & H Sensor" and likely siblings), not to be confused
    # with the unrelated "tdq" reuse of the "kg" sensor descriptors elsewhere.
    "tdq": {
        "temp_current": {
            "dp_id": 27,
            "type": "Integer",
            "values": json.dumps(
                {"unit": "℃", "min": -400, "max": 1000, "scale": 1, "step": 1}
            ),
        },
        "humidity_value": {
            "dp_id": 46,
            "type": "Integer",
            "values": json.dumps(
                {"unit": "%", "min": 0, "max": 100, "scale": 0, "step": 1}
            ),
        },
        "battery_state": {
            "dp_id": 101,
            "type": "Enum",
            "values": json.dumps({"range": ["low", "middle", "high"]}),
        },
    },
    # "hwktwkq" is Tuya's "Smart AC Controller" hub category (product_id
    # 6qvdtaoelxa4k5c5 seen here, likely shared by siblings). The hub has a
    # built-in ambient temperature/humidity sensor feeding its own IR-based
    # AC control loop, but -- same root cause as "tdq" above -- the reading
    # only ever reaches Tuya's newer shadow/properties model, never the
    # legacy DP status cache these dpcodes/scales were read directly off a
    # live device via shadow/properties on 2026-09-07.
    "hwktwkq": {
        "temp_current": {
            "dp_id": 2,
            "type": "Integer",
            "values": json.dumps(
                {"unit": "℃", "min": -400, "max": 1000, "scale": 1, "step": 1}
            ),
        },
        # Key is "humidity_value" (not the device's real dpcode
        # "humidity_current") so this lands on the same, already-recognized
        # generic sensor code as the "tdq" category above -- HA's generic
        # dpcode-to-sensor recognition only fires for a known allowlist of
        # code names, and "humidity_current" isn't on it (silently produces
        # no entity at all, not even a disabled one, unlike "temp_current"
        # which IS recognized). "shadow_code" records the real dpcode name
        # so the value can still be pulled from the shadow/properties
        # response correctly.
        "humidity_value": {
            "dp_id": 12,
            "type": "Integer",
            "shadow_code": "humidity_current",
            "values": json.dumps(
                {"unit": "%", "min": 0, "max": 100, "scale": 0, "step": 1}
            ),
        },
    },
}


class XTSharingDeviceRepository(DeviceRepository):
    def __init__(
        self,
        customer_api: XTSharingAPI,
        manager: sm.XTSharingDeviceManager,
        multi_manager: MultiManager,
    ):
        super().__init__(customer_api)
        self.manager = manager
        self.multi_manager = multi_manager
        self.api = customer_api

    def _fix_infrared_device_specification(self, device: CustomerDevice):
        if device.category.startswith("infrared_"):
            for key, value in device.status_range.items():
                dpcode = None
                if hasattr(value, "code"):
                    dpcode = str(getattr(value, "code"))
                if hasattr(value, "type") and isinstance(getattr(value, "type"), str):
                    setattr(device.status_range[key], "type", "Boolean")
                values = None
                if hasattr(value, "values"):
                    values = getattr(value, "values")
                    if dpcode is not None and dpcode == key:
                        # This is an infrared dpcode, fix the values to be proper json
                        setattr(
                            device.status_range[key],
                            "values",
                            json.dumps({"original_content": values}),
                        )
                        # device.status[key] = False

            for key, value in device.function.items():
                dpcode = None
                if hasattr(value, "code"):
                    dpcode = str(getattr(value, "code"))
                if hasattr(value, "type") and isinstance(getattr(value, "type"), str):
                    setattr(device.function[key], "type", "Boolean")
                values = None
                if hasattr(value, "values"):
                    values = getattr(value, "values")
                    if dpcode is not None and dpcode == key:
                        # This is an infrared dpcode, fix the values to be proper json
                        setattr(
                            device.function[key],
                            "values",
                            json.dumps({"original_content": values}),
                        )
                        # device.status[key] = False

    def _fix_known_category_device_specification(self, device: CustomerDevice):
        """Backfill status_range/function for categories/products whose Tuya
        specification response never included them, using a hardcoded known
        DP layout. Only fills in codes that are genuinely missing so this
        never overrides real data the cloud did provide."""
        known_specs = _KNOWN_CATEGORY_DP_SPECS.get(device.category)
        if not known_specs:
            return
        for code, spec in known_specs.items():
            if code not in device.status_range:
                device.status_range[code] = SimpleNamespace(
                    code=code,
                    type=spec["type"],
                    values=spec["values"],
                    dp_id=spec["dp_id"],
                )
            if code not in device.function:
                device.function[code] = SimpleNamespace(
                    code=code,
                    type=spec["type"],
                    values=spec["values"],
                    dp_id=spec["dp_id"],
                    desc="",
                    name=code,
                )

    def update_device_specification(self, device: CustomerDevice):
        super().update_device_specification(device)

        self._fix_infrared_device_specification(device)
        self._fix_known_category_device_specification(device)

        # Now convert the status_range and function to XT format
        for code in device.status_range:
            device.status_range[code] = (  # type: ignore
                XTDeviceStatusRange.from_compatible_status_range(
                    device.status_range[code]
                )
            )
        for code in device.function:
            device.function[code] = XTDeviceFunction.from_compatible_function(  # type: ignore
                device.function[code]
            )

    def query_devices_by_home(self, home_id: str) -> list[CustomerDevice]:
        try:
            response = self.api.get("/v1.0/m/life/ha/home/devices", {"homeId": home_id})
        except Exception:
            # LOGGER.warning(f"query_devices_by_home exception, removing home {home_id}: {e}")
            self.manager.delete_home(home_id)
            return []
        return self._query_devices(response)

    def _get_shadow_properties(self, device_id: str) -> dict[str, Any]:
        """Fetch the cloud "Things Data Model" shadow properties for a device.

        Some products (e.g. category "tdq" / product_id x3o8epevyeo3z3oa "T & H
        Sensor") never populate the legacy DP status cache used by
        query_devices_by_home/devices/detail, even though the device reports
        fine and the value is visible in the Smart Life app. That data lives
        in the newer shadow/properties model instead, reachable with the same
        sharing-session credentials (no separate OpenAPI project needed).
        """
        try:
            response = self.api.get(f"/v1.0/m/life/ha/{device_id}/shadow/properties")
        except Exception as e:
            LOGGER.debug(f"_get_shadow_properties failed for {device_id}: {e}")
            return {}
        if not response or not response.get("success"):
            return {}
        properties = response.get("result", {}).get("properties", [])
        return {
            p["code"]: p["value"]
            for p in properties
            if "code" in p and "value" in p
        }

    def _query_devices(self, response) -> list[CustomerDevice]:
        _devices = []

        def _query_devices_thread(item) -> None:
            device = CustomerDevice(**item)
            status = {}
            for item_status in device.status:
                if "code" in item_status and "value" in item_status:
                    code = item_status["code"]  # type: ignore
                    value = item_status["value"]  # type: ignore
                    status[code] = value
            known_specs = _KNOWN_CATEGORY_DP_SPECS.get(device.category)
            if known_specs and any(
                code not in status
                and spec.get("shadow_code", code) not in status
                for code, spec in known_specs.items()
            ):
                shadow_status = self._get_shadow_properties(device.id)
                # Merge everything reported, not just the codes we know
                # about -- costs nothing and keeps data (setpoint, mode,
                # fan speed, etc.) available for other code to use later.
                for code, value in shadow_status.items():
                    status.setdefault(code, value)
                # For codes whose real Tuya dpcode isn't on HA's generic
                # sensor allowlist, also expose the value under our
                # "canonical" (recognized) code name.
                for code, spec in known_specs.items():
                    shadow_code = spec.get("shadow_code", code)
                    if code not in status and shadow_code in status:
                        status[code] = status[shadow_code]
            device.status = status
            self.update_device_specification(device)
            self.update_device_strategy_info(device)
            _devices.append(device)

        thread_manager: XTThreadingManager = XTThreadingManager()
        if response["success"]:
            for item in response["result"]:
                thread_manager.add_thread(_query_devices_thread, item=item)
        thread_manager.start_and_wait(max_concurrency=9)
        return _devices

    def _update_device_strategy_info_mod(self, device: CustomerDevice):
        device_id = device.id
        response = self.api.get(f"/v1.0/m/life/devices/{device_id}/status")
        support_local = True
        dp_id_map = {}
        if response.get("success"):
            result = response.get("result", {})
            pid = result["productKey"]
            for dp_status_relation in result["dpStatusRelationDTOS"]:
                if not dp_status_relation["supportLocal"]:
                    support_local = False
                    # break                          #REMOVED
                # statusFormat valueDesc、valueType,enumMappingMap,pid
                if "dpId" in dp_status_relation:  # ADDED
                    dp_id_map[dp_status_relation["dpId"]] = {
                        "value_convert": dp_status_relation["valueConvert"],
                        "status_code": dp_status_relation["statusCode"],
                        "config_item": {
                            "statusFormat": dp_status_relation["statusFormat"],
                            "valueDesc": dp_status_relation["valueDesc"],
                            "valueType": dp_status_relation["valueType"],
                            "enumMappingMap": dp_status_relation["enumMappingMap"],
                            "pid": pid,
                        },  # CHANGED
                        "status_code_alias": [],  # CHANGED
                    }
        known_specs = _KNOWN_CATEGORY_DP_SPECS.get(device.category)
        if known_specs:
            for code, spec in known_specs.items():
                if spec["dp_id"] in dp_id_map:
                    continue
                dp_id_map[spec["dp_id"]] = {
                    "value_convert": "default",
                    "status_code": code,
                    "config_item": {
                        "statusFormat": json.dumps({code: "$"}),
                        "valueDesc": spec["values"],
                        "valueType": spec["type"],
                        "enumMappingMap": {},
                        "pid": device.product_id,
                    },
                    "status_code_alias": [],
                }
        device.support_local = support_local
        # if support_local:                      #CHANGED
        device.local_strategy = dp_id_map  # CHANGED

    def update_device_strategy_info(self, device: CustomerDevice):
        self._update_device_strategy_info_mod(device)
        self.multi_manager.virtual_state_handler.apply_init_virtual_states(device)  # type: ignore

    def send_commands(self, device_id: str, commands: list[dict[str, Any]]):
        return super().send_commands(device_id, commands)
