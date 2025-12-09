from __future__ import annotations
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
                    setattr(device.status_range[key], "type", str(getattr(value, "type")).lower())
                values = None
                if hasattr(value, "values"):
                    values = getattr(value, "values")
                    if dpcode is not None and dpcode == key:
                        #This is an infrared dpcode, fix the values to be proper json
                        setattr(device.status_range[key], "values", json.dumps({"original_content": values}))
            
            for key, value in device.function.items():
                dpcode = None
                if hasattr(value, "code"):
                    dpcode = str(getattr(value, "code"))
                if hasattr(value, "type") and isinstance(getattr(value, "type"), str):
                    setattr(device.function[key], "type", str(getattr(value, "type")).lower())
                values = None
                if hasattr(value, "values"):
                    values = getattr(value, "values")
                    if dpcode is not None and dpcode == key:
                        #This is an infrared dpcode, fix the values to be proper json
                        setattr(device.function[key], "values", json.dumps({"original_content": values}))

    def update_device_specification(self, device: CustomerDevice):
        super().update_device_specification(device)
        
        self._fix_infrared_device_specification(device)

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
        response = self.api.get("/v1.0/m/life/ha/home/devices", {"homeId": home_id})
        return self._query_devices(response)

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
            device.status = status
            self.update_device_specification(device)
            self.update_device_strategy_info(device)
            _devices.append(device)

        thread_manager: XTThreadingManager = XTThreadingManager()
        if response["success"]:
            for item in response["result"]:
                thread_manager.add_thread(_query_devices_thread, item=item)
        thread_manager.start_and_wait(max_concurrency=9)
        for cur_device in _devices:
            self.multi_manager.device_watcher.report_message(cur_device.id, f"_query_devices result: {cur_device}",device=cur_device)
        return _devices

    def _update_device_strategy_info_mod(self, device: CustomerDevice):
        device_id = device.id
        response = self.api.get(f"/v1.0/m/life/devices/{device_id}/status")
        support_local = True
        if response.get("success"):
            result = response.get("result", {})
            pid = result["productKey"]
            dp_id_map = {}
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
            device.support_local = support_local
            # if support_local:                      #CHANGED
            device.local_strategy = dp_id_map  # CHANGED

    def update_device_strategy_info(self, device: CustomerDevice):
        self._update_device_strategy_info_mod(device)
        self.multi_manager.virtual_state_handler.apply_init_virtual_states(device)  # type: ignore

    def send_commands(self, device_id: str, commands: list[dict[str, Any]]):
        return super().send_commands(device_id, commands)
