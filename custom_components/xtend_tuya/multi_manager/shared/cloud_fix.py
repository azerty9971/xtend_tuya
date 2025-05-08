from __future__ import annotations

import json, copy

from .device import (
    XTDevice,
    XTDeviceFunction,
    XTDeviceStatusRange,
)
from ...const import (
    LOGGER,  # noqa: F401
    DPType,
)
from ...entity import (
    XTEntity,
)

class CloudFixes:
    def apply_fixes(device: XTDevice):
        CloudFixes._unify_data_types(device)
        CloudFixes._unify_added_attributes(device)
        CloudFixes._map_dpid_to_codes(device)
        CloudFixes._fix_incorrect_valuedescr(device)
        CloudFixes._fix_incorrect_percentage_scale(device)
        CloudFixes._align_valuedescr(device)
        CloudFixes._fix_missing_local_strategy_enum_mapping_map(device)
        CloudFixes._fix_missing_range_values_using_local_strategy(device)
        CloudFixes._fix_missing_aliases_using_status_format(device)
        CloudFixes._remove_status_that_are_local_strategy_aliases(device)
        CloudFixes._fix_unaligned_function_or_status_range(device)
        
    def fix_incorrect_percent_scale_forced(device: XTDevice, function_code: str):
        recomputed_function_code = function_code
        for dpId in device.local_strategy:
            status_code = device.local_strategy[dpId].get("status_code")
            status_code_aliases = device.local_strategy[dpId].get("status_code_alias", [])
            if status_code != function_code and function_code not in status_code_aliases:
                continue

            #We found the correct status, let's store it
            recomputed_function_code = status_code

            if config_item := device.local_strategy[dpId].get("config_item"):
                if value_descr := config_item.get("valueDesc"):
                    value = json.loads(value_descr)
                    if "unit" in value and "min" in value and "max" in value and "scale" in value:
                        try:
                            max = int(value["max"])
                            if max % 100 != 0:
                                continue
                            scale = 0
                            while max > 100:
                                max = int(max / 10)
                                scale = scale + 1
                            value["scale"] = scale
                            config_item["valueDesc"] = json.dumps(value)
                        except Exception:
                            continue
        if recomputed_function_code in device.status_range:
            value = json.loads(device.status_range[recomputed_function_code].values)
            if "unit" in value and "min" in value and "max" in value and "scale" in value:
                try:
                    max = int(value["max"])
                    if max % 100 == 0:
                        scale = 0
                        while max > 100:
                            max = int(max / 10)
                            scale = scale + 1
                        value["scale"] = scale
                        device.status_range[recomputed_function_code].values = json.dumps(value)
                except Exception:
                    pass
        if recomputed_function_code in device.function:
            value = json.loads(device.function[recomputed_function_code].values)
            if "unit" in value and "min" in value and "max" in value and "scale" in value:
                try:
                    max = int(value["max"])
                    if max % 100 == 0:
                        scale = 0
                        while max > 100:
                            max = int(max / 10)
                            scale = scale + 1
                        value["scale"] = scale
                        device.function[recomputed_function_code].values = json.dumps(value)
                except Exception:
                    pass

    def _fix_unaligned_function_or_status_range(device: XTDevice):

        #Remove status_ranges that are refering to an alias
        status_push: dict[str, XTDeviceStatusRange] = {}
        status_pop: list[str] = []
        for status in device.status_range:
            dp_id: int = device.status_range[status].dp_id
            if dp_id in device.local_strategy:
                if strat_code := device.local_strategy[dp_id].get("status_code"):
                    if strat_code != status:
                        if strat_code not in device.status_range and strat_code not in device.function:
                            status_push[strat_code] = copy.deepcopy(device.status_range[status])
                            status_push[strat_code].code = strat_code
                        #Merge to be removed status_range in local strategy
                        if config_item := device.local_strategy[dp_id].get("config_item"):
                            if value_descr := config_item.get("valueDesc"):
                                ls_value, _ = CloudFixes.get_value_descr_dict(value_descr)
                                if ls_value is not None:
                                    sr_value, _ = CloudFixes.get_value_descr_dict(device.status_range[status].values)
                                    fix_dict = CloudFixes.compute_aligned_valuedescr(ls_value, sr_value, {})
                                    for fix_code in fix_dict:
                                        ls_value[fix_code] = fix_dict[fix_code]
                                    config_item["valueDesc"] = json.dumps(ls_value)
                                    if strat_code in device.status_range:
                                        device.status_range[strat_code].values = config_item["valueDesc"]
                                    if strat_code in device.function:
                                        device.function[strat_code].values = config_item["valueDesc"]
                        status_pop.append(status)
        for status in status_pop:
            device.status_range.pop(status)
        for status in status_push:
            device.status_range[status] = status_push[status]
        
        #Remove functions that are refering to an alias
        function_push: dict[str, XTDeviceFunction] = {}
        function_pop: list[str] = []
        for function in device.function:
            dp_id: int = device.function[function].dp_id
            if dp_id in device.local_strategy:
                if strat_code := device.local_strategy[dp_id].get("status_code"):
                    if strat_code != function:
                        if strat_code not in device.status_range and strat_code not in device.function:
                            function_push[strat_code] = copy.deepcopy(device.function[function])
                            function_push[strat_code].code = strat_code
                        #Merge to be removed function in local strategy
                        if config_item := device.local_strategy[dp_id].get("config_item"):
                            if value_descr := config_item.get("valueDesc"):
                                ls_value, _ = CloudFixes.get_value_descr_dict(value_descr)
                                if ls_value is not None:
                                    fn_value, _ = CloudFixes.get_value_descr_dict(device.function[function].values)
                                    fix_dict = CloudFixes.compute_aligned_valuedescr(ls_value, fn_value, {})
                                    for fix_code in fix_dict:
                                        ls_value[fix_code] = fix_dict[fix_code]
                                    config_item["valueDesc"] = json.dumps(ls_value)
                                    if strat_code in device.status_range:
                                        device.status_range[strat_code].values = config_item["valueDesc"]
                                    if strat_code in device.function:
                                        device.function[strat_code].values = config_item["valueDesc"]
                        function_pop.append(function)
        for function in function_pop:
            device.function.pop(function)
        for function in function_push:
            device.function[function] = function_push[function]

    def _unify_added_attributes(device: XTDevice):
        for dpId in device.local_strategy:
            if device.local_strategy[dpId].get("property_update") is None:
                device.local_strategy[dpId]["property_update"] = False
            if device.local_strategy[dpId].get("use_open_api") is None:
                device.local_strategy[dpId]["use_open_api"] = False
            if device.local_strategy[dpId].get("status_code_alias") is None:
                device.local_strategy[dpId]["status_code_alias"] = []
    
    def _unify_data_types(device: XTDevice):
        for key in device.status_range:
            if not isinstance(device.status_range[key], XTDeviceStatusRange):
                device.status_range[key] = XTDeviceStatusRange.from_compatible_status_range(device.status_range[key])
            device.status_range[key].type = XTEntity.determine_dptype(device.status_range[key].type)
        for key in device.function:
            if not isinstance(device.function[key], XTDeviceFunction):
                device.function[key] = XTDeviceFunction.from_compatible_function(device.function[key])
            device.function[key].type = XTEntity.determine_dptype(device.function[key].type)
        for dpId in device.local_strategy:
            if config_item := device.local_strategy[dpId].get("config_item"):
                if "valueType" in config_item and "valueDesc" in config_item:
                    config_item["valueType"] = XTEntity.determine_dptype(config_item["valueType"])
                    if code := device.local_strategy[dpId].get("status_code"):
                        state_value = device.status.get(code)
                        second_pass = False
                        if code in device.status_range:
                            match CloudFixes.determine_most_plausible(config_item, {"valueType": device.status_range[code].type}, "valueType", state_value):
                                case 1:
                                    device.status_range[code].type = config_item["valueType"]
                                    device.status_range[code].values = config_item["valueDesc"]
                                case 2:
                                    config_item["valueType"] = device.status_range[code].type
                                    config_item["valueDesc"] = device.status_range[code].values
                        if code in device.function:
                            match CloudFixes.determine_most_plausible(config_item, {"valueType": device.function[code].type}, "valueType", state_value):
                                case 1:
                                    device.function[code].type = config_item["valueType"]
                                    device.function[code].values = config_item["valueDesc"]
                                case 2:
                                    config_item["valueType"] = device.function[code].type
                                    config_item["valueDesc"] = device.function[code].values
                                    second_pass = True
                        if second_pass:
                            if code in device.status_range:
                                match CloudFixes.determine_most_plausible(config_item, {"valueType": device.status_range[code].type}, "valueType", state_value):
                                    case 1:
                                        device.status_range[code].type = config_item["valueType"]
                                        device.status_range[code].values = config_item["valueDesc"]
                                    case 2:
                                        config_item["valueType"] = device.status_range[code].type
                                        config_item["valueDesc"] = device.status_range[code].values
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
            if aliases := dp_item.get("status_code_alias"):
                for alias in aliases:
                    if alias not in all_codes:
                        all_codes.append(alias)
        for code in all_codes:
            correct_value = None
            dp_id = None
            need_fixing = False
            sr_need_fixing = False
            fn_need_fixing = False
            ls_need_fixing = False
            if code in device.status_range:
                sr_value_dict, sr_value_raw = CloudFixes.get_value_descr_dict(device.status_range[code].values)
                if device.status_range[code].dp_id is not None:
                    dp_id = device.status_range[code].dp_id
                if sr_value_dict is None:
                    sr_need_fixing = True
                    need_fixing = True
                else:
                    correct_value = sr_value_raw
            if code in device.function:
                fn_value_dict, fn_value_raw = CloudFixes.get_value_descr_dict(device.function[code].values)
                if device.function[code].dp_id is not None:
                    dp_id = device.function[code].dp_id
                if fn_value_dict is None:
                    fn_need_fixing = True
                    need_fixing = True
                else:
                    correct_value = fn_value_raw
            if dp_id is None:
                #Try to find the code the manually (Should not happen in theory)
                for dp_id_temp in device.local_strategy:
                    if ls_code := device.local_strategy[dp_id_temp].get("status_code"):
                        if ls_code == code:
                            dp_id = dp_id_temp
                            break
                    if aliases := device.local_strategy[dp_id_temp].get("status_code_alias"):
                        for alias in aliases:
                            if alias == code:
                                dp_id = dp_id_temp
                                break
            if dp_id is not None:
                if dp_item := device.local_strategy.get(dp_id):
                    if config_item := dp_item.get("config_item"):
                        ls_value_dict, ls_value_raw = CloudFixes.get_value_descr_dict(config_item.get("valueDesc"))
                        if ls_value_dict is None:
                            ls_need_fixing = True
                            need_fixing = True
                        else:
                            correct_value = ls_value_raw

            if need_fixing:
                if correct_value is None:
                    error_values: list[str] = []
                    if ls_need_fixing:
                        error_values.append(ls_value_raw)
                    if sr_need_fixing:
                        error_values.append(sr_value_raw)
                    if fn_need_fixing:
                        error_values.append(fn_value_raw)
                    if len(error_values) < 2:
                        correct_value = CloudFixes.get_fixed_value_descr(error_values[0], None)
                    else:
                        correct_value = CloudFixes.get_fixed_value_descr(error_values[0], error_values[1])
                if sr_need_fixing:
                    device.status_range[code].values = correct_value
                if fn_need_fixing:
                    device.function[code].values = correct_value
                if ls_need_fixing:
                    config_item["valueDesc"] = correct_value

    def get_value_descr_dict(value_str: str):
        try:
            value_dict: dict = json.loads(value_str)
            if value_dict.get("ErrorValue1"):
                return None, value_dict["ErrorValue1"]
            iter(value_dict)
            return value_dict, value_str
        except Exception:
            return None, value_str
    
    def get_fixed_value_descr(value1_str: str, value2_str: str | None = None) -> str:
        if value1_str is not None and value2_str is not None:
            return json.dumps({
                "ErrorValue1": value1_str,
                "ErrorValue2": value2_str,
            })
        elif value1_str is not None:
            return json.dumps({
                "ErrorValue1": value1_str,
            })
        elif value2_str is not None:
            return json.dumps({
                "ErrorValue1": value2_str,
            })
        else:
            return json.dumps({})

    def _align_valuedescr(device: XTDevice):
        all_codes: dict[str, int] = {}
        for code in device.status_range:
            if code not in all_codes:
                all_codes[code] = 1
            else:
                all_codes[code] += 1
        for code in device.function:
            if code not in all_codes:
                all_codes[code] = 1
            else:
                all_codes[code] += 1
        for dp_item in device.local_strategy.values():
            if code := dp_item.get("status_code"):
                if code not in all_codes:
                    all_codes[code] = 1
                else:
                    all_codes[code] += 1
        for code in all_codes:
            if all_codes[code] < 2:
                continue
            sr_value = None
            fn_value = None
            ls_value = None
            dp_id = None
            if code in device.status_range:
                sr_value = json.loads(device.status_range[code].values)
                dp_id = device.status_range[code].dp_id
            if code in device.function:
                fn_value = json.loads(device.function[code].values)
                dp_id = device.function[code].dp_id
            if dp_id is not None:
                if dp_item := device.local_strategy.get(dp_id):
                    if config_item := dp_item.get("config_item"):
                        if value_descr := config_item.get("valueDesc"):
                            ls_value = json.loads(value_descr)
            fix_dict = CloudFixes.compute_aligned_valuedescr(ls_value, sr_value, fn_value)
            for fix_code in fix_dict:
                if sr_value is not None:
                    sr_value[fix_code] = fix_dict[fix_code]
                if fn_value is not None:
                    fn_value[fix_code] = fix_dict[fix_code]
                if ls_value is not None:
                    ls_value[fix_code] = fix_dict[fix_code]
            if sr_value:
                device.status_range[code].values = json.dumps(sr_value)
            if fn_value:
                device.function[code].values = json.dumps(fn_value)
            if ls_value:
                config_item["valueDesc"] = json.dumps(ls_value)

    
    def compute_aligned_valuedescr(value1: dict, value2: dict, value3: dict) -> dict:
        return_dict: dict = {}
        maxlen_list: list = CloudFixes._get_field_of_valuedescr(value1, value2, value3, "maxlen")
        if len(maxlen_list) > 0:
            maxlen_cur = int(maxlen_list[0])
            for maxlen in maxlen_list:
                maxlen = int(maxlen)
                if maxlen > maxlen_cur:
                    maxlen_cur = maxlen
            return_dict["maxlen"] = maxlen_cur
        min_list: list = CloudFixes._get_field_of_valuedescr(value1, value2, value3, "min")
        if len(min_list) > 0:
            min_cur = int(min_list[0])
            for min in min_list:
                min = int(min)
                if min < min_cur:
                    min_cur = min
            return_dict["min"] = min_cur
        max_list: list = CloudFixes._get_field_of_valuedescr(value1, value2, value3, "max")
        if len(max_list) > 0:
            max_cur = int(max_list[0])
            for max in max_list:
                max = int(max)
                if max > max_cur:
                    max_cur = max
            return_dict["max"] = max_cur
        scale_list: list = CloudFixes._get_field_of_valuedescr(value1, value2, value3, "scale")
        if len(scale_list) > 0:
            scale_cur = int(scale_list[0])
            for scale in scale_list:
                scale = int(scale)
                if scale > scale_cur:
                    scale_cur = scale
            return_dict["scale"] = scale_cur
        step_list: list = CloudFixes._get_field_of_valuedescr(value1, value2, value3, "step")
        if len(step_list) > 0:
            step_cur = int(step_list[0])
            for step in step_list:
                step = int(step)
                if step < step_cur:
                    step_cur = step
            return_dict["step"] = step_cur
        range_list: list = CloudFixes._get_field_of_valuedescr(value1, value2, value3, "range")
        if len(range_list) > 1:
            range_ref:list = range_list[0]
            for range in range_list[1:]:
                #Determine if the range should be merged or not

                #We should only add the range values if they overlap
                new_item: int = 0
                overlap_item: int = 0
                for item in range:
                    if item in range_ref:
                        overlap_item += 1
                    else:
                        new_item += 1
                if new_item > 0 and overlap_item > 1:
                    for item in range:
                        if item not in range_ref:
                            range_ref.append(item)
            return_dict["range"] = range_ref
        return return_dict
            

    def _get_field_of_valuedescr(value1: dict, value2: dict, value3: dict, field: str) -> list:
        return_list: list = []
        if value1:
            value = value1.get(field)
            if value is not None and value not in return_list:
                return_list.append(value)
        if value2:
            value = value2.get(field)
            if value is not None and value not in return_list:
                return_list.append(value)
        if value3:
            value = value3.get(field)
            if value is not None and value not in return_list:
                return_list.append(value)
        return return_list
        

    def _fix_incorrect_percentage_scale(device: XTDevice):
        supported_units: list = ["%"]
        for code in device.status_range:
            value = json.loads(device.status_range[code].values)
            if "unit" in value and "min" in value and "max" in value and "scale" in value:
                unit = value["unit"]
                try:
                    min = int(value["min"])
                    max = int(value["max"])
                    if unit not in supported_units:
                        continue
                    if max % 100 != 0:
                        continue
                    scale = 0
                    while max > 100:
                        max = int(max / 10)
                        scale = scale + 1
                    value["scale"] = scale
                    device.status_range[code].values = json.dumps(value)
                except Exception:
                    continue
        for code in device.function:
            value = json.loads(device.function[code].values)
            if "unit" in value and "min" in value and "max" in value and "scale" in value:
                unit = value["unit"]
                try:
                    min = int(value["min"])
                    max = int(value["max"])
                    if unit not in supported_units:
                        continue
                    if max % 100 != 0:
                        continue
                    scale = 0
                    while max > 100:
                        max = int(max / 10)
                        scale = scale + 1
                    value["scale"] = scale
                    device.function[code].values = json.dumps(value)
                except Exception:
                    continue
        for dpId in device.local_strategy:
            if config_item := device.local_strategy[dpId].get("config_item"):
                if value_descr := config_item.get("valueDesc"):
                    value = json.loads(value_descr)
                    if "unit" in value and "min" in value and "max" in value and "scale" in value:
                        unit = value["unit"]
                        try:
                            min = int(value["min"])
                            max = int(value["max"])
                            if unit not in supported_units:
                                continue
                            if max % 100 != 0:
                                continue
                            scale = 0
                            while max > 100:
                                max = int(max / 10)
                                scale = scale + 1
                            value["scale"] = scale
                            config_item["valueDesc"] = json.dumps(value)
                        except Exception:
                            continue

    def determine_most_plausible(value1: dict, value2: dict, key: str, state_value: any = None) -> int | None:
        if key in value1 and key in value2:
            if value1[key] == value2[key]:
                return None
            if not value1[key]:
                return 2
            if not value2[key]:
                return 1
            if value1[key] == DPType.RAW and XTEntity.determine_dptype(value2[key]) is not None and isinstance(value1[key], DPType):
                return 2
            if value2[key] == DPType.RAW and XTEntity.determine_dptype(value1[key]) is not None and isinstance(value2[key], DPType):
                return 1
            if value1[key] == DPType.STRING and value2[key] == DPType.JSON and isinstance(value1[key], DPType) and isinstance(value2[key], DPType):
                return 2
            if value2[key] == DPType.STRING and value1[key] == DPType.JSON and isinstance(value1[key], DPType) and isinstance(value2[key], DPType):
                return 1
            if value1[key] == DPType.BOOLEAN and state_value in ["True", "False", "true", "false", True, False] and isinstance(value1[key], DPType):
                return 1
            if value2[key] == DPType.BOOLEAN and state_value in ["True", "False", "true", "false", True, False] and isinstance(value2[key], DPType):
                return 2
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
                                status_range_range_dict: list = status_range_values.get("range", {})
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
                                function_range_dict: list = function_values.get("range", {})
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
                        if status != status_code:
                            if status not in local_strategy["status_code_alias"]:
                                local_strategy["status_code_alias"].append(status)
                            pop_list.append(status)
                    for status in pop_list:
                        status_formats_dict.pop(status)
                    if status_code not in status_formats_dict:
                        status_formats_dict[status_code] = "$"
                    config_item["statusFormat"] = json.dumps(status_formats_dict)
    
    def _remove_status_that_are_local_strategy_aliases(device: XTDevice):
        for local_strategy in device.local_strategy.values():
            code = local_strategy.get("status_code")
            if aliases := local_strategy.get("status_code_alias", None):
                for alias in aliases:
                    poped_value = None
                    if alias in device.status:
                        poped_value = device.status.pop(alias)
                    if code is not None:
                        remapped_alias = False
                        if alias in device.status_range and code not in device.status_range:
                            device.status_range[code] = device.status_range[alias]
                            device.status_range[code].code = code
                            remapped_alias = True
                        if alias in device.function and code not in device.function:
                            device.function[code] = device.function[alias]
                            device.function[code].code = code
                            remapped_alias = True
                        if remapped_alias:
                            device.status[code] = poped_value