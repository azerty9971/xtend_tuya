from __future__ import annotations

import json

from .device import (
    XTDevice,
)

class CloudFixes:
    def apply_fixes(device: XTDevice):
        CloudFixes._fix_missing_local_strategy_enum_mapping_map(device)
        CloudFixes._fix_missing_scale_using_local_strategy(device)
        CloudFixes._fix_incorrect_percentage_scale(device)
        CloudFixes._fix_missing_range_values_using_local_strategy(device)
        CloudFixes._fix_missing_aliases_using_status_format(device)
        CloudFixes._remove_status_that_are_local_strategy_aliases(device)

    def _fix_incorrect_percentage_scale(device: XTDevice):
        for code in device.status_range:
            value = json.loads(device.status_range[code].values)
            if "unit" in value and "min" in value and "max" in value and "scale" in value:
                unit = value["unit"]
                min = value["min"]
                max = value["max"]
                if unit not in ("%"):
                    continue
                if max % 100 != 0:
                    continue
                if min not in (0, 1):
                    continue
                value["scale"] = int(max / 100) - 1
                device.status_range[code].values = json.dumps(value)
        for code in device.function:
            value = json.loads(device.function[code].values)
            if "unit" in value and "min" in value and "max" in value and "scale" in value:
                unit = value["unit"]
                min = value["min"]
                max = value["max"]
                if unit not in ("%"):
                    continue
                if max % 100 != 0:
                    continue
                if min not in (0, 1):
                    continue
                value["scale"] = int(max / 100) - 1
                device.function[code].values = json.dumps(value)
    
    def _fix_missing_scale_using_local_strategy(device: XTDevice):
        for local_strategy in device.local_strategy.values():
            if "status_code" not in local_strategy:
                continue
            code = local_strategy["status_code"]
            if config_item := local_strategy.get("config_item", None):
                if valueDesc := config_item.get("valueDesc", None):
                    if code in device.status_range:
                        value1 = json.loads(valueDesc)
                        value2 = json.loads(device.status_range[code].values)
                        match CloudFixes._determine_most_plausible(value1, value2, "scale"):
                            case None:
                                match CloudFixes._determine_most_plausible(value1, value2, "min"):
                                    case None:
                                        pass
                                    case 1:
                                        device.status_range[code].values = valueDesc
                            case 1:
                                device.status_range[code].values = valueDesc
                    if code in device.function:
                        value1 = json.loads(valueDesc)
                        value2 = json.loads(device.function[code].values)
                        match CloudFixes._determine_most_plausible(value1, value2, "scale"):
                            case None:
                                match CloudFixes._determine_most_plausible(value1, value2, "min"):
                                    case None:
                                        pass
                                    case 1:
                                        device.function[code].values = valueDesc
                            case 1:
                                device.function[code].values = valueDesc

    def _determine_most_plausible(value1: dict, value2: dict, key: str) -> int | None:
        if key in value1 and key in value2:
            if value1[key] == value2[key]:
                return None
            if not value1[key]:
                return 2
            if not value2[key]:
                return 1
            return None

        elif key in value1:
            return 1
        elif key in value2:
            return 2
        return None

    def _fix_missing_local_strategy_enum_mapping_map(device: XTDevice):
        for local_strategy in device.local_strategy.values():
            if config_item := local_strategy.get("config_item", None):
                if mappings := config_item.get("enumMappingMap", None):
                    if 'false' in mappings and str(False) not in mappings:
                        mappings[str(False)] = mappings['false']
                    if 'true' in mappings and str(True) not in mappings:
                        mappings[str(True)] = mappings['true']
    
    def _fix_missing_range_values_using_local_strategy(device: XTDevice):
        for local_strategy in device.local_strategy.values():
            status_code = local_strategy.get("status_code", None)
            if status_code not in device.status_range and status_code not in device.function:
                continue
            if config_item := local_strategy.get("config_item", None):
                if config_item.get("valueType", None) != "Enum":
                    continue
                if valueDesc := config_item.get("valueDesc", None):
                    value_dict = json.loads(valueDesc)
                    if valueDescr_range := value_dict.get("range", {}):
                        if status_range := device.status_range.get(status_code, None):
                            if status_range_values := json.loads(status_range.values):
                                status_range_range_dict: list = status_range_values.get("range")
                                new_range_list: list = []
                                for new_range_value in valueDescr_range:
                                    new_range_list.append(new_range_value)
                                for new_range_value in status_range_range_dict:
                                    if new_range_value not in new_range_list:
                                        new_range_list.append(new_range_value)
                                status_range_values["range"] = new_range_list
                                status_range.values = json.dumps(status_range_values)


    def _fix_missing_aliases_using_status_format(device: XTDevice):
        for local_strategy in device.local_strategy.values():
            status_code = local_strategy.get("status_code", None)
            if config_item := local_strategy.get("config_item", None):
                if status_formats := config_item.get("statusFormat", None):
                    status_formats_dict = json.loads(status_formats)
                    for status in status_formats_dict:
                        if status != status_code and status not in local_strategy["status_code_alias"]:
                            local_strategy["status_code_alias"].append(status)
    
    def _remove_status_that_are_local_strategy_aliases(device: XTDevice):
        for local_strategy in device.local_strategy.values():
            if aliases := local_strategy.get("status_code_alias", None):
                for alias in aliases:
                    if alias in device.status:
                        device.status.pop(alias)