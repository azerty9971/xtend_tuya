from __future__ import annotations

from tuya_sharing.customerapi import (
    CustomerApi,
)

from tuya_sharing.device import (
    CustomerDevice,
    DeviceRepository,
    DeviceStatusRange,
)

from ...const import (
    LOGGER,  # noqa: F401
)

from .xt_tuya_sharing_manager import (
    XTSharingDeviceManager,
)

from ..multi_manager import (
    MultiManager,
)
from ..shared.device import (
    XTDeviceFunction,
    XTDeviceStatusRange,
)

class XTSharingDeviceRepository(DeviceRepository):
    def __init__(self, customer_api: CustomerApi, manager: XTSharingDeviceManager, multi_manager: MultiManager):
        super().__init__(customer_api)
        self.manager = manager
        self.multi_manager = multi_manager

    def update_device_specification(self, device: CustomerDevice):
        super().update_device_specification(device)

        #Now convert the status_range and function to XT format
        for code in device.status_range:
            device.status_range[code] = XTDeviceStatusRange.from_compatible_status_range(device.status_range[code])
        for code in device.function:
            device.function[code] = XTDeviceFunction.from_compatible_function(device.function[code])

    def query_devices_by_home(self, home_id: str) -> list[CustomerDevice]:
        response = self.api.get("/v1.0/m/life/ha/home/devices", {"homeId": home_id})
        return self._query_devices(response)
    
    def _query_devices(self, response) -> list[CustomerDevice]:
        _devices = []
        if response["success"]:
            for item in response["result"]:
                device = CustomerDevice(**item)
                status = {}
                for item_status in device.status:
                    if "code" in item_status and "value" in item_status:
                        code = item_status["code"]
                        value = item_status["value"]
                        status[code] = value
                device.status = status
                self.update_device_specification(device)
                self.update_device_strategy_info(device)
                _devices.append(device)
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
                    #break                          #REMOVED
                # statusFormat valueDesc、valueType,enumMappingMap,pid
                if "dpId" in dp_status_relation:    #ADDED
                    dp_id_map[dp_status_relation["dpId"]] = {
                        "value_convert": dp_status_relation["valueConvert"],
                        "status_code": dp_status_relation["statusCode"],
                        "config_item": {
                            "statusFormat": dp_status_relation["statusFormat"],
                            "valueDesc": dp_status_relation["valueDesc"],
                            "valueType": dp_status_relation["valueType"],
                            "enumMappingMap": dp_status_relation["enumMappingMap"],
                            "pid": pid,
                        },                              #CHANGED
                        "status_code_alias": []         #CHANGED
                    }
            device.support_local = support_local
            #if support_local:                      #CHANGED
            device.local_strategy = dp_id_map       #CHANGED

    def update_device_strategy_info(self, device: CustomerDevice):
        #super().update_device_strategy_info(device)
        self._update_device_strategy_info_mod(device)
        #Sometimes the Type provided by Tuya is ill formed,
        #replace it with the one from the local strategy
        # for loc_strat in device.local_strategy.values():
        #     if "statusCode" not in loc_strat or "valueType" not in loc_strat:
        #         continue
        #     code = loc_strat["statusCode"]
        #     value_type = loc_strat["valueType"]

        #     if code in device.status_range:
        #         device.status_range[code].type = value_type
        #     if code in device.function:
        #         device.function[code].type     = value_type

        #     if (
        #         "valueDesc"  in loc_strat and
        #         code not in device.status_range and
        #         code not in device.function
        #         ):
        #         device.status_range[code] = DeviceStatusRange()   #CHANGED
        #         device.status_range[code].code   = code
        #         device.status_range[code].type   = value_type
        #         device.status_range[code].values = loc_strat["valueDesc"]

        self.multi_manager.virtual_state_handler.apply_init_virtual_states(device)