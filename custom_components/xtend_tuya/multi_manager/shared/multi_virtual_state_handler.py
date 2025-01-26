from __future__ import annotations

import copy

from homeassistant.helpers.entity import EntityDescription

from .device import (
    XTDevice,
)

from ...const import (
    VirtualStates,
    DescriptionVirtualState,
    LOGGER,  # noqa: F401
)

from ..multi_manager import (
    MultiManager,
)

class XTVirtualStateHandler:
    def __init__(self, multi_manager: MultiManager) -> None:
        self.descriptors_with_virtual_state = {}
        self.multi_manager = multi_manager

    def register_device_descriptors(self, name: str, descriptors):
        descriptors_with_vs = {}
        for category in descriptors:
            description_list_vs: list = []
            category_item = descriptors[category]
            if isinstance(category_item, tuple):
                for description in category_item:
                    if hasattr(description, "virtual_state") and description.virtual_state is not None:
                        description_list_vs.append(description)
                    
            elif isinstance(category_item, EntityDescription):
                #category is directly a descriptor
                if hasattr(category_item, "virtual_state") and category_item.virtual_state is not None:
                    description_list_vs.append(category_item)

            if len(description_list_vs) > 0:
                    descriptors_with_vs[category] = tuple(description_list_vs)
        if len(descriptors_with_vs) > 0:
            self.descriptors_with_virtual_state[name] = descriptors_with_vs
            for device in self.multi_manager.device_map.values():
                self.apply_init_virtual_states(device)

    def get_category_virtual_states(self,category: str) -> list[DescriptionVirtualState]:
        to_return = []
        for virtual_state in VirtualStates:
            for descriptor in self.descriptors_with_virtual_state.values():
                if (descriptions := descriptor.get(category)):
                    for description in descriptions:
                        if description.virtual_state is not None and description.virtual_state & virtual_state.value:
                            # This virtual_state is applied to this key, let's return it
                            found_virtual_state = DescriptionVirtualState(description.key, virtual_state.name, virtual_state.value, description.vs_copy_to_state, description.vs_copy_delta_to_state)
                            to_return.append(found_virtual_state)
        return to_return

    def apply_init_virtual_states(self, device: XTDevice):
        #WARNING, this method might be called multiple times for the same device, make sure it doesn't
        #fail upon multiple successive calls
        virtual_states = self.get_category_virtual_states(device.category)
        for virtual_state in virtual_states:
            if virtual_state.virtual_state_value == VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME:
                if virtual_state.key in device.status:
                    if virtual_state.key in device.status_range:
                        for vs_new_code in virtual_state.vs_copy_to_state:
                            new_code = str(vs_new_code)
                            if device.status.get(new_code, None) is None:
                                device.status[new_code] = copy.deepcopy(device.status[virtual_state.key])
                            device.status_range[new_code] = copy.deepcopy(device.status_range[virtual_state.key])
                            device.status_range[new_code].code = new_code
                            device.status_range[new_code].dp_id = None
                            if not self.multi_manager._read_dpId_from_code(new_code, device):
                                if dp_id := self.multi_manager._read_dpId_from_code(virtual_state.key, device):
                                    if new_dp_id := self._get_empty_local_strategy_dp_id(device):
                                        new_local_strategy = copy.deepcopy(device.local_strategy[dp_id])
                                        if "config_item" in new_local_strategy:
                                            new_local_strategy_config_item = new_local_strategy["config_item"]
                                            if "statusFormat" in new_local_strategy_config_item and virtual_state.key in new_local_strategy_config_item["statusFormat"]:
                                                new_local_strategy_config_item["statusFormat"] = new_local_strategy_config_item["statusFormat"].replace(virtual_state.key, new_code)
                                        new_local_strategy["status_code"] = new_code
                                        device.local_strategy[new_dp_id] = new_local_strategy
                                        device.status_range[new_code].dp_id = new_dp_id
                        for vs_new_code in virtual_state.vs_copy_delta_to_state:
                            new_code = str(vs_new_code)
                            if device.status.get(new_code, None) is None:
                                device.status[new_code] = 0
                            device.status_range[new_code] = copy.deepcopy(device.status_range[virtual_state.key])
                            device.status_range[new_code].code = new_code
                            device.status_range[new_code].dp_id = None
                            if not self.multi_manager._read_dpId_from_code(new_code, device):
                                if dp_id := self.multi_manager._read_dpId_from_code(virtual_state.key, device):
                                    if new_dp_id := self._get_empty_local_strategy_dp_id(device):
                                        new_local_strategy = copy.deepcopy(device.local_strategy[dp_id])
                                        if "config_item" in new_local_strategy:
                                            new_local_strategy_config_item = new_local_strategy["config_item"]
                                            if "statusFormat" in new_local_strategy_config_item and virtual_state.key in new_local_strategy_config_item["statusFormat"]:
                                                new_local_strategy_config_item["statusFormat"] = new_local_strategy_config_item["statusFormat"].replace(virtual_state.key, new_code)
                                        new_local_strategy["status_code"] = new_code
                                        device.local_strategy[new_dp_id] = new_local_strategy
                                        device.status_range[new_code].dp_id = new_dp_id
                    if virtual_state.key in device.function:
                        for vs_new_code in virtual_state.vs_copy_to_state:
                            new_code = str(vs_new_code)
                            if device.status.get(new_code, None) is None:
                                device.status[new_code] = copy.deepcopy(device.status[virtual_state.key])
                            device.function[new_code] = copy.deepcopy(device.function[virtual_state.key])
                            device.function[new_code].code = new_code
                            device.function[new_code].dp_id = None
                            if not self.multi_manager._read_dpId_from_code(new_code, device):
                                if dp_id := self.multi_manager._read_dpId_from_code(virtual_state.key, device):
                                    if new_dp_id := self._get_empty_local_strategy_dp_id(device):
                                        new_local_strategy = copy.deepcopy(device.local_strategy[dp_id])
                                        new_local_strategy["status_code"] = new_code
                                        device.local_strategy[new_dp_id] = new_local_strategy
                                        device.function[new_code].dp_id = new_dp_id

    def apply_virtual_states_to_status_list(self, device: XTDevice, status_in: list, source: str = None) -> list:
        status = copy.deepcopy(status_in)
        virtual_states = self.get_category_virtual_states(device.category)
        debug: bool = False
        for virtual_state in virtual_states:
            if virtual_state.virtual_state_value == VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME:
                for item in status:
                    code, dpId, new_key_value, result_ok = self.multi_manager._read_code_dpid_value_from_state(device.id, item)
                    if result_ok and code == "add_ele":
                        if not debug:
                            self.multi_manager.device_watcher.report_message(device.id, f"[{source}]Status In: {status_in}", device)
                        debug = True
                        #self.multi_manager.device_watcher.report_message(device.id, f"VirtualStates: {virtual_states}", device)
                        
                    if result_ok and code == virtual_state.key:
                        cur_key_value = 0
                        if code in device.status:
                            cur_key_value = device.status[code]
                        for state_name in virtual_state.vs_copy_to_state:
                            code, dpId, new_key_value, result_ok = self.multi_manager._read_code_dpid_value_from_state(device.id, {"code": str(state_name), "value": new_key_value})
                            if result_ok:
                                new_status = {"code": code, "value": copy.copy(new_key_value), "dpId": dpId}
                                status.append(new_status)
                        for state_name in virtual_state.vs_copy_delta_to_state:
                            code, dpId, new_key_value, result_ok = self.multi_manager._read_code_dpid_value_from_state(device.id, {"code": str(state_name), "value": new_key_value})
                            current_value = None
                            if code in device.status:
                                current_value = device.status[code]
                            if result_ok and current_value is not None:
                                new_status = {"code": code, "value": copy.copy(new_key_value - cur_key_value), "dpId": dpId}
                                status.append(new_status)
            
            if virtual_state.virtual_state_value == VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD:
                if virtual_state.key not in device.status:
                    continue
                if device.status[virtual_state.key] is None:
                    device.status[virtual_state.key] = 0
                if virtual_state.key in device.status:
                    for item in status:
                        code, dpId, new_key_value, result_ok = self.multi_manager._read_code_dpid_value_from_state(device.id, item, False, True)
                        if result_ok and code == virtual_state.key:
                            item["value"] += device.status[virtual_state.key]
                            continue
        if debug:
            self.multi_manager.device_watcher.report_message(device.id, f"[{source}]Status Out: {status}", device)
        return status
    
    def _get_empty_local_strategy_dp_id(self, device: XTDevice) -> int | None:
        if not hasattr(device, "local_strategy"):
            return None
        base_id = 10000
        while True:
            if base_id in device.local_strategy:
                base_id += 1
                continue
            return base_id