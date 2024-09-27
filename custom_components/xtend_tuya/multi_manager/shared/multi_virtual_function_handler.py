from __future__ import annotations

from typing import Any

from homeassistant.helpers.entity import EntityDescription

from ...const import (
    VirtualFunctions,
    DescriptionVirtualFunction,
)

from .device import (
    XTDevice,
)

from ..multi_manager import (
    MultiManager,
)

class XTVirtualFunctionHandler:
    def __init__(self, multi_manager: MultiManager) -> None:
        self.descriptors_with_virtual_function = {}
        self.multi_manager = multi_manager
    
    def register_device_descriptors(self, name: str, descriptors):
        descriptors_with_vf = {}
        for category in descriptors:
            description_list_vf: list = []
            category_item = descriptors[category]
            if isinstance(category_item, tuple):
                for description in category_item:
                    if hasattr(description, "virtual_function") and description.virtual_function is not None:
                        description_list_vf.append(description)
                    
            elif isinstance(category_item, EntityDescription):
                #category is directly a descriptor
                if hasattr(category_item, "virtual_function") and category_item.virtual_function is not None:
                    description_list_vf.append(category_item)

            if len(description_list_vf) > 0:
                    descriptors_with_vf[category] = tuple(description_list_vf)

        if len(descriptors_with_vf) > 0:
            self.descriptors_with_virtual_function[name] = descriptors_with_vf
    
    def get_category_virtual_functions(self,category: str) -> list[DescriptionVirtualFunction]:
        to_return = []
        for virtual_function in VirtualFunctions:
            for descriptor in self.descriptors_with_virtual_function.values():
                if (descriptions := descriptor.get(category)):
                    for description in descriptions:
                        if description.virtual_function is not None and description.virtual_function & virtual_function.value:
                            # This virtual_state is applied to this key, let's return it
                            found_virtual_function = DescriptionVirtualFunction(description.key, virtual_function.name, virtual_function.value, description.vf_reset_state)
                            to_return.append(found_virtual_function)
        return to_return
    
    def process_virtual_function(self, device_id: str, commands: list[dict[str, Any]]):
        device: XTDevice = self.multi_manager.device_map.get(device_id, None)
        if not device:
            return
        for command in commands:
            virtual_function: DescriptionVirtualFunction = command["virtual_function"]
            """command_code: str = command["code"]
            command_value: Any = command["value"]"""
            if virtual_function.virtual_function_value == VirtualFunctions.FUNCTION_RESET_STATE:
                for state_to_reset in virtual_function.vf_reset_state:
                    if state_to_reset in device.status:
                        device.status[state_to_reset] = 0
                        self.multi_manager.multi_device_listener.update_device(device)
                        break