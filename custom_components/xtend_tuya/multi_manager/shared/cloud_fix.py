from __future__ import annotations

import json

from .device import (
    XTDevice,
    XTDeviceFunction,
    XTDeviceStatusRange,
)
from ...const import (
    LOGGER,  # noqa: F401
)
from ...base import (
    DPType,
    TuyaEntity,
)

class CloudFixes:
    def apply_fixes(device: XTDevice):
        CloudFixes._unify_data_types(device)
        CloudFixes._unify_added_attributes(device)
        CloudFixes._map_dpid_to_codes(device)
        CloudFixes._fix_incorrect_valuedescr(device)
        CloudFixes._fix_missing_local_strategy_enum_mapping_map(device)
        CloudFixes._fix_missing_scale_using_local_strategy(device)
        CloudFixes._fix_incorrect_percentage_scale(device)
        CloudFixes._fix_missing_range_values_using_local_strategy(device)
        CloudFixes._fix_missing_aliases_using_status_format(device)
        CloudFixes._remove_status_that_are_local_strategy_aliases(device)

    def _unify_added_attributes(device: XTDevice):
        for dpId in device.local_strategy:
            if device.local_strategy[dpId].get("property_update") is None:
                device.local_strategy[dpId]["property_update"] = False
            if device.local_strategy[dpId].get("use_open_api") is None:
                device.local_strategy[dpId]["use_open_api"] = False
    
    def _unify_data_types(device: XTDevice):
        for key in device.status_range:
            if not isinstance(device.status_range[key], XTDeviceStatusRange):
                device.status_range[key] = XTDeviceStatusRange.from_compatible_status_range(device.status_range[key])
            device.status_range[key].type = TuyaEntity.determine_dptype(device.status_range[key].type)
        for key in device.function:
            if not isinstance(device.function[key], XTDeviceFunction):
                device.function[key] = XTDeviceFunction.from_compatible_function(device.function[key])
            device.function[key].type = TuyaEntity.determine_dptype(device.function[key].type)
        for dpId in device.local_strategy:
            if config_item := device.local_strategy[dpId].get("config_item"):
                if "valueType" in config_item:
                    config_item["valueType"] = TuyaEntity.determine_dptype(config_item["valueType"])
                    if code := device.local_strategy[dpId].get("status_code"):
                        second_pass = False
                        if code in device.status_range:
                            match CloudFixes.determine_most_plausible(config_item, {"valueType": device.status_range[code].type}, "valueType"):
                                case 1:
                                    device.status_range[code].type = config_item["valueType"]
                                case 2:
                                    config_item["valueType"] = device.status_range[code].type
                        if code in device.function:
                            match CloudFixes.determine_most_plausible(config_item, {"valueType": device.function[code].type}, "valueType"):
                                case 1:
                                    device.function[code].type = config_item["valueType"]
                                case 2:
                                    config_item["valueType"] = device.function[code].type
                                    second_pass = True
                        if second_pass:
                            if code in device.status_range:
                                match CloudFixes.determine_most_plausible(config_item, {"valueType": device.status_range[code].type}, "valueType"):
                                    case 1:
                                        device.status_range[code].type = config_item["valueType"]
                                    case 2:
                                        config_item["valueType"] = device.status_range[code].type
    
    def _map_dpid_to_codes(device: XTDevice):
        for dpId in device.local_strategy:
            if code := device.local_strategy[dpId].get("status_code"):
                if code in device.function:
                    device.function[code].dp_id = dpId
                if code in device.status_range:
                    device.status_range[code].dp_id = dpId
            if code_alias := device.local_strategy[dpId].get("status_code_alias"):
                for code in code_alias:
                    if code in device.function:
                        device.function[code].dp_id = dpId
                    if code in device.status_range:
                        device.status_range[code].dp_id = dpId

    def _fix_incorrect_valuedescr(device: XTDevice):
        all_codes: list[str] = []
        for code in device.status_range:
            if code not in all_codes:
                all_codes.append(code)
        for code in device.function:
            if code not in all_codes:
                all_codes.append(code)
        for dp_item in device.local_strategy.values():
            if code := dp_item.get("status_code"):
                if code not in all_codes:
                    all_codes.append(code)
        for code in all_codes:
            correct_value = None
            dp_id = None
            need_fixing = False
            sr_need_fixing = False
            fn_need_fixing = False
            ls_need_fixing = False
            try:
                if code in device.status_range:
                    dp_id = device.status_range[code].dp_id
                    json.loads(device.status_range[code].values)
                    correct_value = device.status_range[code].values
            except Exception:
                sr_need_fixing = True
                need_fixing = True
            try:
                if code in device.function:
                    dp_id = device.function[code].dp_id
                    json.loads(device.function[code].values)
                    correct_value = device.function[code].values
            except Exception:
                fn_need_fixing = True
                need_fixing = True
            if dp_id is not None:
                try:
                    if dp_item := device.local_strategy.get(dp_id):
                        if config_item := dp_item.get("config_item"):
                            if value_descr := config_item.get("valueDesc"):
                                json.loads(value_descr)
                except Exception:
                    ls_need_fixing = True
                    need_fixing = True
            if need_fixing and correct_value is not None:
                if sr_need_fixing:
                    device.status_range[code].values = correct_value
                if fn_need_fixing:
                    device.function[code].values = correct_value
                if ls_need_fixing:
                    config_item["valueDesc"] = correct_value

    def _fix_incorrect_percentage_scale(device: XTDevice):
        for code in device.status_range:
            value = json.loads(device.status_range[code].values)
            if "unit" in value and "min" in value and "max" in value and "scale" in value:
                unit = value["unit"]
                min = value["min"]
                max = value["max"]
                if unit not in ["%"]:
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
                        match CloudFixes.determine_most_plausible(value1, value2, "scale"):
                            case None:
                                match CloudFixes.determine_most_plausible(value1, value2, "min"):
                                    case None:
                                        pass
                                    case 1:
                                        device.status_range[code].values = valueDesc
                            case 1:
                                device.status_range[code].values = valueDesc
                    if code in device.function:
                        value1 = json.loads(valueDesc)
                        value2 = json.loads(device.function[code].values)
                        match CloudFixes.determine_most_plausible(value1, value2, "scale"):
                            case None:
                                match CloudFixes.determine_most_plausible(value1, value2, "min"):
                                    case None:
                                        pass
                                    case 1:
                                        device.function[code].values = valueDesc
                            case 1:
                                device.function[code].values = valueDesc

    def determine_most_plausible(value1: dict, value2: dict, key: str) -> int | None:
        if key in value1 and key in value2:
            if value1[key] == value2[key]:
                return None
            if not value1[key]:
                return 2
            if not value2[key]:
                return 1
            if value1[key] == DPType.RAW and TuyaEntity.determine_dptype(value2[key]) is not None and isinstance(value1[key], DPType):
                return 2
            if value2[key] == DPType.RAW and TuyaEntity.determine_dptype(value1[key]) is not None and isinstance(value2[key], DPType):
                return 1
            if value1[key] == DPType.STRING and value2[key] == DPType.JSON and isinstance(value1[key], DPType) and isinstance(value2[key], DPType):
                return 2
            if value2[key] == DPType.STRING and value1[key] == DPType.JSON and isinstance(value1[key], DPType) and isinstance(value2[key], DPType):
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
                        if function := device.function.get(status_code, None):
                            if function_values := json.loads(function.values):
                                function_range_dict: list = function_values.get("range")
                                new_range_list: list = []
                                for new_range_value in valueDescr_range:
                                    new_range_list.append(new_range_value)
                                for new_range_value in function_range_dict:
                                    if new_range_value not in new_range_list:
                                        new_range_list.append(new_range_value)
                                function_values["range"] = new_range_list
                                function.values = json.dumps(function_values)


    def _fix_missing_aliases_using_status_format(device: XTDevice):
        for local_strategy in device.local_strategy.values():
            status_code = local_strategy.get("status_code", None)
            if config_item := local_strategy.get("config_item", None):
                if status_formats := config_item.get("statusFormat", None):
                    status_formats_dict: dict = json.loads(status_formats)
                    pop_list: list[str] = []
                    for status in status_formats_dict:
                        if status != status_code and status not in local_strategy["status_code_alias"]:
                            pop_list.append(status)
                            local_strategy["status_code_alias"].append(status)
                    for status in pop_list:
                        status_formats_dict.pop(status)
                    config_item["statusFormat"] = json.dumps(status_formats_dict)
    
    def _remove_status_that_are_local_strategy_aliases(device: XTDevice):
        for local_strategy in device.local_strategy.values():
            if aliases := local_strategy.get("status_code_alias", None):
                for alias in aliases:
                    if alias in device.status:
                        device.status.pop(alias)