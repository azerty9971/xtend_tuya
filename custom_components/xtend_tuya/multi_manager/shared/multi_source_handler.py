from __future__ import annotations
import copy

from ..multi_manager import MultiManager
from ...const import LOGGER  # noqa: F401

class SourceCodeCounter:
    def __init__(self, source: str) -> None:
        self.source = source
        self.counter = 1

class MultiSourceCodeCounter:
    def __init__(self) -> None:
        self.source_counter_list: list[SourceCodeCounter] = []
        self.last_allowed_source = None
    
    def register_source_message(self, source: str):
        source_counter_found = False
        for source_counter in self.source_counter_list:
            if source_counter.source == source:
                source_counter.counter += 1
                source_counter_found = True
                break
        
        if not source_counter_found:
            self.source_counter_list.append(SourceCodeCounter(source))
    
    def get_allowed_source(self) -> str:
        last_allowed_source_count = 0
        highest_source_count = 0
        highest_source = None
        for source_counter in self.source_counter_list:
            if source_counter.source == self.last_allowed_source:
                last_allowed_source_count = source_counter.counter
            if source_counter.counter > highest_source_count:
                highest_source_count = source_counter.counter
                highest_source = source_counter.source

        if self.last_allowed_source is None:
            self.last_allowed_source = highest_source
            return highest_source
        
        if ( highest_source_count - last_allowed_source_count ) > 1:
            self.last_allowed_source = highest_source
            return highest_source
        else:
            return self.last_allowed_source


class MultiSourceHandler:
    def __init__(self, multi_manager: MultiManager) -> None:
        self.multi_manager = multi_manager
        self.device_map: dict[str, dict[str, MultiSourceCodeCounter]] = {}
    
    def register_status_list_from_source(self, dev_id: str, source: str, status_in) -> None:
        device = self.multi_manager.device_map.get(dev_id, None)
        if not device:
            return
        
        virtual_states = self.multi_manager.virtual_state_handler.get_category_virtual_states(device.category)
        if not virtual_states:
            return
        
        for item in status_in:
            code, dpId, value, result_ok = self.multi_manager._read_code_dpid_value_from_state(dev_id, item, False, True)
            if not result_ok:
                continue

            for virtual_state in virtual_states:
                if code == virtual_state.key:
                    self._prepare_structure_for_code(dev_id, code)
                    self.device_map[dev_id][code].register_source_message(source)

    def filter_status_list(self, dev_id: str, original_source: str, status_in) -> str:
        status_list = copy.deepcopy(status_in)
        device = self.multi_manager.device_map.get(dev_id, None)
        if not device:
            return status_list
        
        #Only filter for devices that have a VirtualState in their status_list
        virtual_states = self.multi_manager.virtual_state_handler.get_category_virtual_states(device.category)
        if not virtual_states:
            return status_list
        
        i = 0
        for item in status_list:
            code, dpId, value, result_ok = self.multi_manager._read_code_dpid_value_from_state(dev_id, item, False, True)
            if not result_ok:
                continue

            for virtual_state in virtual_states:
                if code == virtual_state.key:
                    self._prepare_structure_for_code(dev_id, code)
                    if not self._is_allowed_source_for_code(dev_id, code, original_source):
                        status_list.pop(i)
                        i -= 1
                        break
            i += 1
        
        return status_list
    
    def _prepare_structure_for_code(self, dev_id:str, code: str) -> None:
        if dev_id not in self.device_map:
            self.device_map[dev_id] = {}
        if code not in self.device_map[dev_id]:
            self.device_map[dev_id][code] = MultiSourceCodeCounter()

    def _is_allowed_source_for_code(self, dev_id: str, code: str, source: str) -> bool:
        return self.device_map[dev_id][code].get_allowed_source() == source