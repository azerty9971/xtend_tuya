from __future__ import annotations
import json
import copy
from typing import Any
from .shared_classes import (
    XTDevice,
    XTDeviceFunction,
    XTDeviceStatusRange,
)
from ...ha_tuya_integration.tuya_integration_imports import (
    TuyaDPType,
    tuya_util_parse_dptype,
)
from ...const import (
    UOM_MAPPING_DICT,
    LOGGER,
)
import custom_components.xtend_tuya.multi_manager.multi_manager as mm


class CloudFixes:
    @staticmethod
    def apply_fixes(device: XTDevice, multi_manager: mm.MultiManager | None = None):
        if multi_manager is not None:
            multi_manager.device_watcher.report_message(
                device.id,
                f"CloudFixes for source {device.source} BEFORE: {device}",
                device=device,
            )
        CloudFixes._unify_data_types(device)
        CloudFixes._unify_added_attributes(device)
        CloudFixes._map_dpid_to_codes(device)
        CloudFixes._fix_incorrect_valuedescr(device)
        CloudFixes._fix_incorrect_percentage_scale(device)
        CloudFixes._align_valuedescr(device)
        CloudFixes._fix_missing_local_strategy_enum_mapping_map(device)
        CloudFixes._fix_missing_range_values_using_data_model(device)
        CloudFixes._fix_missing_range_values_using_local_strategy(device)
        CloudFixes._fix_missing_aliases_using_status_format(device)
        CloudFixes._remove_status_that_are_local_strategy_aliases(device)
        CloudFixes._fix_unaligned_function_or_status_range(device)
        CloudFixes._strip_valuedescr_of_non_label_fields_for_bitmaps(device)
        CloudFixes._fix_isolated_status_range_and_function(device)
        CloudFixes._align_uom(device)
        if multi_manager is not None:
            multi_manager.device_watcher.report_message(
                device.id,
                f"CloudFixes for source {device.source} AFTER: {device}",
                device=device,
            )

    @staticmethod
    def fix_incorrect_percent_scale_forced(
        device: XTDevice, function_code: str, scale_threshold: int = 100
    ):
        recomputed_function_code = function_code
        for dpId in device.local_strategy:
            status_code = device.local_strategy[dpId].get("status_code")
            status_code_aliases = device.local_strategy[dpId].get(
                "status_code_alias", []
            )
            if (
                status_code != function_code
                and function_code not in status_code_aliases
            ):
                continue

            # We found the correct status, let's store it
            recomputed_function_code = status_code

            if config_item := device.local_strategy[dpId].get("config_item"):
                if value_descr := config_item.get("valueDesc"):
                    value = json.loads(value_descr)
                    if "min" in value and "max" in value and "scale" in value:
                        try:
                            max = int(value["max"])
                            scale = 0
                            while max > scale_threshold:
                                max = int(max / 10)
                                scale = scale + 1
                            value["scale"] = scale
                            config_item["valueDesc"] = json.dumps(value)
                        except Exception:
                            continue
        if recomputed_function_code in device.status_range:
            value = json.loads(device.status_range[recomputed_function_code].values)
            if "min" in value and "max" in value and "scale" in value:
                try:
                    max = int(value["max"])
                    scale = 0
                    while max > scale_threshold:
                        max = int(max / 10)
                        scale = scale + 1
                    value["scale"] = scale
                    device.status_range[recomputed_function_code].values = json.dumps(
                        value
                    )
                except Exception:
                    pass
        if recomputed_function_code in device.function:
            value = json.loads(device.function[recomputed_function_code].values)
            if "min" in value and "max" in value and "scale" in value:
                try:
                    max = int(value["max"])
                    scale = 0
                    while max > scale_threshold:
                        max = int(max / 10)
                        scale = scale + 1
                    value["scale"] = scale
                    device.function[recomputed_function_code].values = json.dumps(value)
                except Exception:
                    pass

    @staticmethod
    def _strip_valuedescr_of_non_label_fields_for_bitmaps(device: XTDevice):
        for _, status in device.status_range.items():
            if status.type == TuyaDPType.BITMAP:
                values_dict = json.loads(status.values)
                if "label" in values_dict:
                    values_dict = {"label": values_dict["label"]}
                else:
                    values_dict = {}
                status.values = json.dumps(values_dict)
        for _, function in device.function.items():
            if function.type == TuyaDPType.BITMAP:
                values_dict = json.loads(function.values)
                if "label" in values_dict:
                    values_dict = {"label": values_dict["label"]}
                else:
                    values_dict = {}
                function.values = json.dumps(values_dict)
        for _, ls in device.local_strategy.items():
            if config_item := ls.get("config_item"):
                ls_type = config_item.get("valueType")
                if ls_type == TuyaDPType.BITMAP:
                    if value_descr := config_item.get("valueDesc"):
                        values_dict = json.loads(value_descr)
                        if "label" in values_dict:
                            values_dict = {"label": values_dict["label"]}
                        else:
                            values_dict = {}
                        config_item["valueDesc"] = json.dumps(values_dict)

    @staticmethod
    def _fix_isolated_status_range_and_function(device: XTDevice):
        # Remove status_ranges and functions that are not linked to any local strategy item
        status_range_pop: list[str] = []
        for status in device.status_range:
            dp_id: int = device.status_range[status].dp_id
            if dp_id == 0 or dp_id not in device.local_strategy:
                status_range_pop.append(status)
        for status in status_range_pop:
            device.status_range.pop(status)
        function_pop: list[str] = []
        for function in device.function:
            dp_id: int = device.function[function].dp_id
            if dp_id == 0 or dp_id not in device.local_strategy:
                function_pop.append(function)
        for function in function_pop:
            device.function.pop(function)

    @staticmethod
    def _fix_unaligned_function_or_status_range(device: XTDevice):
        # Remove status_ranges that are refering to an alias
        status_push: dict[str, XTDeviceStatusRange] = {}
        status_pop: list[str] = []
        for status in device.status_range:
            dp_id: int = device.status_range[status].dp_id
            if dp_id in device.local_strategy:
                if strat_code := device.local_strategy[dp_id].get("status_code"):
                    if strat_code != status:
                        if (
                            strat_code not in device.status_range
                            and strat_code not in device.function
                        ):
                            status_push[strat_code] = copy.deepcopy(
                                device.status_range[status]
                            )
                            status_push[strat_code].code = strat_code
                        # Merge to be removed status_range in local strategy
                        if config_item := device.local_strategy[dp_id].get(
                            "config_item"
                        ):
                            if value_descr := config_item.get("valueDesc"):
                                ls_value, _ = CloudFixes.get_value_descr_dict(
                                    value_descr
                                )
                                if ls_value is not None:
                                    sr_value, _ = CloudFixes.get_value_descr_dict(
                                        device.status_range[status].values
                                    )
                                    fix_dict = CloudFixes.compute_aligned_valuedescr(
                                        ls_value, sr_value, {}
                                    )
                                    for fix_code in fix_dict:
                                        ls_value[fix_code] = fix_dict[fix_code]
                                    config_item["valueDesc"] = json.dumps(ls_value)
                                    if strat_code in device.status_range:
                                        device.status_range[
                                            strat_code
                                        ].values = config_item["valueDesc"]
                                    if strat_code in device.function:
                                        device.function[
                                            strat_code
                                        ].values = config_item["valueDesc"]
                        status_pop.append(status)
        for status in status_pop:
            device.status_range.pop(status)
        for status in status_push:
            device.status_range[status] = status_push[status]

        # Remove functions that are refering to an alias
        function_push: dict[str, XTDeviceFunction] = {}
        function_pop: list[str] = []
        for function in device.function:
            dp_id: int = device.function[function].dp_id
            if dp_id in device.local_strategy:
                if strat_code := device.local_strategy[dp_id].get("status_code"):
                    if strat_code != function:
                        if (
                            strat_code not in device.status_range
                            and strat_code not in device.function
                        ):
                            function_push[strat_code] = copy.deepcopy(
                                device.function[function]
                            )
                            function_push[strat_code].code = strat_code
                        # Merge to be removed function in local strategy
                        if config_item := device.local_strategy[dp_id].get(
                            "config_item"
                        ):
                            if value_descr := config_item.get("valueDesc"):
                                ls_value, _ = CloudFixes.get_value_descr_dict(
                                    value_descr
                                )
                                if ls_value is not None:
                                    fn_value, _ = CloudFixes.get_value_descr_dict(
                                        device.function[function].values
                                    )
                                    fix_dict = CloudFixes.compute_aligned_valuedescr(
                                        ls_value, fn_value, {}
                                    )
                                    for fix_code in fix_dict:
                                        ls_value[fix_code] = fix_dict[fix_code]
                                    config_item["valueDesc"] = json.dumps(ls_value)
                                    if strat_code in device.status_range:
                                        device.status_range[
                                            strat_code
                                        ].values = config_item["valueDesc"]
                                    if strat_code in device.function:
                                        device.function[
                                            strat_code
                                        ].values = config_item["valueDesc"]
                        function_pop.append(function)
        for function in function_pop:
            device.function.pop(function)
        for function in function_push:
            device.function[function] = function_push[function]

    @staticmethod
    def _unify_added_attributes(device: XTDevice):
        for dpId in device.local_strategy:
            if device.local_strategy[dpId].get("property_update") is None:
                device.local_strategy[dpId]["property_update"] = False
            if device.local_strategy[dpId].get("use_open_api") is None:
                device.local_strategy[dpId]["use_open_api"] = False
            if device.local_strategy[dpId].get("status_code_alias") is None:
                device.local_strategy[dpId]["status_code_alias"] = []

    @staticmethod
    def _unify_data_types(device: XTDevice):
        for key in device.status_range:
            if not isinstance(device.status_range[key], XTDeviceStatusRange):
                device.status_range[key] = (
                    XTDeviceStatusRange.from_compatible_status_range(
                        device.status_range[key]
                    )
                )
            device.status_range[key].type = tuya_util_parse_dptype(
                str(device.status_range[key].type)
            )
        for key in device.function:
            if not isinstance(device.function[key], XTDeviceFunction):
                device.function[key] = XTDeviceFunction.from_compatible_function(
                    device.function[key]
                )
            device.function[key].type = tuya_util_parse_dptype(
                str(device.function[key].type)
            )
        for dpId in device.local_strategy:
            if config_item := device.local_strategy[dpId].get("config_item"):
                if "valueType" in config_item and "valueDesc" in config_item:
                    config_item["valueType"] = tuya_util_parse_dptype(
                        config_item["valueType"]
                    )
                    if code := device.local_strategy[dpId].get("status_code"):
                        state_value = device.status.get(code)
                        second_pass = False
                        if code in device.status_range:
                            match CloudFixes.determine_most_plausible(
                                config_item,
                                {"valueType": device.status_range[code].type},
                                "valueType",
                                state_value,
                            ):
                                case 1:
                                    device.status_range[code].type = config_item[
                                        "valueType"
                                    ]
                                    device.status_range[code].values = config_item[
                                        "valueDesc"
                                    ]
                                case 2:
                                    config_item["valueType"] = device.status_range[
                                        code
                                    ].type
                                    config_item["valueDesc"] = device.status_range[
                                        code
                                    ].values
                        if code in device.function:
                            match CloudFixes.determine_most_plausible(
                                config_item,
                                {"valueType": device.function[code].type},
                                "valueType",
                                state_value,
                            ):
                                case 1:
                                    device.function[code].type = config_item[
                                        "valueType"
                                    ]
                                    device.function[code].values = config_item[
                                        "valueDesc"
                                    ]
                                case 2:
                                    config_item["valueType"] = device.function[
                                        code
                                    ].type
                                    config_item["valueDesc"] = device.function[
                                        code
                                    ].values
                                    second_pass = True
                        if second_pass:
                            if code in device.status_range:
                                match CloudFixes.determine_most_plausible(
                                    config_item,
                                    {"valueType": device.status_range[code].type},
                                    "valueType",
                                    state_value,
                                ):
                                    case 1:
                                        device.status_range[code].type = config_item[
                                            "valueType"
                                        ]
                                        device.status_range[code].values = config_item[
                                            "valueDesc"
                                        ]
                                    case 2:
                                        config_item["valueType"] = device.status_range[
                                            code
                                        ].type
                                        config_item["valueDesc"] = device.status_range[
                                            code
                                        ].values

    @staticmethod
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

    @staticmethod
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
            ls_value_raw = ""
            sr_value_raw = ""
            fn_value_raw = ""
            config_item = None
            if code in device.status_range:
                sr_value_dict, sr_value_raw = CloudFixes.get_value_descr_dict(
                    device.status_range[code].values
                )
                if device.status_range[code].dp_id != 0:
                    dp_id = device.status_range[code].dp_id
                if sr_value_dict is None:
                    sr_need_fixing = True
                    need_fixing = True
                else:
                    correct_value = sr_value_raw
            if code in device.function:
                fn_value_dict, fn_value_raw = CloudFixes.get_value_descr_dict(
                    device.function[code].values
                )
                if device.function[code].dp_id != 0:
                    dp_id = device.function[code].dp_id
                if fn_value_dict is None:
                    fn_need_fixing = True
                    need_fixing = True
                else:
                    correct_value = fn_value_raw
            if dp_id is None:
                # Try to find the code the manually (Should not happen in theory)
                for dp_id_temp in device.local_strategy:
                    if ls_code := device.local_strategy[dp_id_temp].get("status_code"):
                        if ls_code == code:
                            dp_id = dp_id_temp
                            break
                    if aliases := device.local_strategy[dp_id_temp].get(
                        "status_code_alias"
                    ):
                        for alias in aliases:
                            if alias == code:
                                dp_id = dp_id_temp
                                break
            if dp_id is not None:
                if dp_item := device.local_strategy.get(dp_id):
                    if config_item := dp_item.get("config_item"):
                        ls_value_dict, ls_value_raw = CloudFixes.get_value_descr_dict(
                            config_item.get("valueDesc")
                        )
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
                        correct_value = CloudFixes.get_fixed_value_descr(
                            error_values[0], None
                        )
                    else:
                        correct_value = CloudFixes.get_fixed_value_descr(
                            error_values[0], error_values[1]
                        )
                if sr_need_fixing:
                    device.status_range[code].values = correct_value
                if fn_need_fixing:
                    device.function[code].values = correct_value
                if ls_need_fixing and config_item is not None:
                    config_item["valueDesc"] = correct_value

    @staticmethod
    def get_value_descr_dict(value_str: str) -> tuple[dict[str, Any] | None, str]:
        try:
            value_dict: dict = json.loads(value_str)
            if value_dict.get("ErrorValue1"):
                return None, value_dict["ErrorValue1"]
            iter(value_dict)
            return value_dict, value_str
        except Exception:
            return None, value_str

    @staticmethod
    def get_fixed_value_descr(
        value1_str: str | None, value2_str: str | None = None
    ) -> str:
        if value1_str is not None and value2_str is not None:
            return json.dumps(
                {
                    "ErrorValue1": value1_str,
                    "ErrorValue2": value2_str,
                }
            )
        elif value1_str is not None:
            return json.dumps(
                {
                    "ErrorValue1": value1_str,
                }
            )
        elif value2_str is not None:
            return json.dumps(
                {
                    "ErrorValue1": value2_str,
                }
            )
        else:
            return json.dumps({})

    @staticmethod
    def _align_uom(device: XTDevice):
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
            sr_uom = None
            fn_value = None
            fn_uom = None
            ls_value = None
            ls_uom = None
            dp_id = None
            config_item = None
            all_uom: list[str] = []
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
            if sr_value and "unit" in sr_value:
                sr_uom = sr_value["unit"]
                if sr_uom in UOM_MAPPING_DICT:
                    sr_uom = UOM_MAPPING_DICT[sr_uom]
                sr_value["unit"] = sr_uom
                if sr_uom is not None and sr_uom not in all_uom:
                    all_uom.append(sr_uom)
            if fn_value and "unit" in fn_value:
                fn_uom = fn_value["unit"]
                if fn_uom in UOM_MAPPING_DICT:
                    fn_uom = UOM_MAPPING_DICT[fn_uom]
                fn_value["unit"] = fn_uom
                if fn_uom is not None and fn_uom not in all_uom:
                    all_uom.append(fn_uom)
            if ls_value and "unit" in ls_value:
                ls_uom = ls_value["unit"]
                if ls_uom in UOM_MAPPING_DICT:
                    ls_uom = UOM_MAPPING_DICT[ls_uom]
                ls_value["unit"] = ls_uom
                if ls_uom is not None and ls_uom not in all_uom:
                    all_uom.append(ls_uom)
            if len(all_uom) > 1:
                LOGGER.warning(f"Multiple different uom found for code {code} on device {device.name}: {all_uom}")
            if sr_value is not None:
                device.status_range[code].values = json.dumps(sr_value)
            if fn_value is not None:
                device.function[code].values = json.dumps(fn_value)
            if ls_value is not None and config_item is not None:
                config_item["valueDesc"] = json.dumps(ls_value)
            
            

    @staticmethod
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
            config_item = None
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
            fix_dict = CloudFixes.compute_aligned_valuedescr(
                ls_value, sr_value, fn_value
            )
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
            if ls_value and config_item is not None:
                config_item["valueDesc"] = json.dumps(ls_value)

    @staticmethod
    def compute_aligned_valuedescr(
        value1: dict[str, Any] | None,
        value2: dict[str, Any] | None,
        value3: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return_dict: dict[str, Any] = {}
        maxlen_list: list = CloudFixes._get_field_of_valuedescr(
            value1, value2, value3, "maxlen"
        )
        if len(maxlen_list) > 0:
            maxlen_cur = int(maxlen_list[0])
            for maxlen in maxlen_list:
                maxlen = int(maxlen)
                if maxlen > maxlen_cur:
                    maxlen_cur = maxlen
            return_dict["maxlen"] = maxlen_cur
        min_list: list = CloudFixes._get_field_of_valuedescr(
            value1, value2, value3, "min"
        )
        if len(min_list) > 0:
            min_cur = int(min_list[0])
            for min in min_list:
                min = int(min)
                if min < min_cur:
                    min_cur = min
            return_dict["min"] = min_cur
        max_list: list = CloudFixes._get_field_of_valuedescr(
            value1, value2, value3, "max"
        )
        if len(max_list) > 0:
            max_cur = int(max_list[0])
            for max in max_list:
                max = int(max)
                if max > max_cur:
                    max_cur = max
            return_dict["max"] = max_cur
        scale_list: list = CloudFixes._get_field_of_valuedescr(
            value1, value2, value3, "scale"
        )
        if len(scale_list) > 0:
            scale_cur = int(scale_list[0])
            for scale in scale_list:
                scale = int(scale)
                if scale > scale_cur:
                    scale_cur = scale
            return_dict["scale"] = scale_cur
        step_list: list = CloudFixes._get_field_of_valuedescr(
            value1, value2, value3, "step"
        )
        if len(step_list) > 0:
            step_cur = int(step_list[0])
            for step in step_list:
                step = int(step)
                if step < step_cur:
                    step_cur = step
            return_dict["step"] = step_cur
        range_list: list = CloudFixes._get_field_of_valuedescr(
            value1, value2, value3, "range"
        )
        if len(range_list) > 1:
            range_ref: list = range_list[0]
            for range in range_list[1:]:
                # Determine if the range should be merged or not

                # We should only add the range values if they overlap
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

    @staticmethod
    def _get_field_of_valuedescr(
        value1: dict[str, Any] | None,
        value2: dict[str, Any] | None,
        value3: dict[str, Any] | None,
        field: str,
    ) -> list:
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

    @staticmethod
    def _fix_incorrect_percentage_scale(device: XTDevice):
        supported_units: list = ["%"]
        for code in device.status_range:
            value = json.loads(device.status_range[code].values)
            if (
                "unit" in value
                and "min" in value
                and "max" in value
                and "scale" in value
            ):
                unit = value["unit"]
                try:
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
            if (
                "unit" in value
                and "min" in value
                and "max" in value
                and "scale" in value
            ):
                unit = value["unit"]
                try:
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
                    if (
                        "unit" in value
                        and "min" in value
                        and "max" in value
                        and "scale" in value
                    ):
                        unit = value["unit"]
                        try:
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

    @staticmethod
    def determine_most_plausible(
        value1: dict, value2: dict, key: str, state_value: Any = None
    ) -> int | None:
        if key in value1 and key in value2:
            if value1[key] == value2[key]:
                return None
            if not value1[key]:
                return 2
            if not value2[key]:
                return 1
            if (
                value1[key] == TuyaDPType.RAW
                and tuya_util_parse_dptype(value2[key]) is not None
                and isinstance(value1[key], TuyaDPType)
            ):
                return 2
            if (
                value2[key] == TuyaDPType.RAW
                and tuya_util_parse_dptype(value1[key]) is not None
                and isinstance(value2[key], TuyaDPType)
            ):
                return 1
            if (
                value1[key] == TuyaDPType.STRING
                and value2[key] == TuyaDPType.JSON
                and isinstance(value1[key], TuyaDPType)
                and isinstance(value2[key], TuyaDPType)
            ):
                return 2
            if (
                value2[key] == TuyaDPType.STRING
                and value1[key] == TuyaDPType.JSON
                and isinstance(value1[key], TuyaDPType)
                and isinstance(value2[key], TuyaDPType)
            ):
                return 1
            if (
                value1[key] == TuyaDPType.BOOLEAN
                and state_value in ["True", "False", "true", "false", True, False]
                and isinstance(value1[key], TuyaDPType)
            ):
                return 1
            if (
                value2[key] == TuyaDPType.BOOLEAN
                and state_value in ["True", "False", "true", "false", True, False]
                and isinstance(value2[key], TuyaDPType)
            ):
                return 2
            return None

        elif key in value1:
            return 1
        elif key in value2:
            return 2
        return None

    @staticmethod
    def _fix_missing_local_strategy_enum_mapping_map(device: XTDevice):
        for local_strategy in device.local_strategy.values():
            if config_item := local_strategy.get("config_item", None):
                if mappings := config_item.get("enumMappingMap", None):
                    if "false" in mappings and str(False) not in mappings:
                        mappings[str(False)] = mappings["false"]
                    if "true" in mappings and str(True) not in mappings:
                        mappings[str(True)] = mappings["true"]

    @staticmethod
    def _fix_missing_range_values_using_data_model(device: XTDevice):
        for service in device.data_model.get("services", {}):
            for property in service.get("properties", {}):
                if (
                    "abilityId" in property
                ):
                    dp_id = int(property["abilityId"])
                    typeSpec = property.get("typeSpec", {})
                    if dp_id not in device.local_strategy:
                        continue
                    local_strategy = device.local_strategy[dp_id]
                    config_item: dict[str, Any] | None = local_strategy.get("config_item", None)
                    if config_item is None:
                        continue
                    if config_item.get("valueType", None) != "Enum":
                        continue
                    valueDesc = config_item.get("valueDesc")
                    if valueDesc is None:
                        continue
                    value_dict: dict[str, Any] = json.loads(valueDesc)
                    valueDescr_range: list = value_dict.get("range", [])
                    for range_value in typeSpec.get("range", []):
                        if range_value not in valueDescr_range:
                            valueDescr_range.append(range_value)
                    value_dict["range"] = valueDescr_range
                    config_item["valueDesc"] = json.dumps(value_dict)
                    

    
    @staticmethod
    def _fix_missing_range_values_using_local_strategy(device: XTDevice):
        for local_strategy in device.local_strategy.values():
            status_code = local_strategy.get("status_code", None)
            if (
                status_code not in device.status_range
                and status_code not in device.function
            ):
                continue
            if config_item := local_strategy.get("config_item", None):
                if config_item.get("valueType", None) != "Enum":
                    continue
                if valueDesc := config_item.get("valueDesc", None):
                    value_dict = json.loads(valueDesc)
                    if valueDescr_range := value_dict.get("range", []):
                        if status_range := device.status_range.get(status_code, None):
                            if status_range_values := json.loads(status_range.values):
                                status_range_range_dict: list = status_range_values.get(
                                    "range", []
                                )
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
                                function_range_dict: list = function_values.get(
                                    "range", []
                                )
                                new_range_list: list = []
                                for new_range_value in valueDescr_range:
                                    new_range_list.append(new_range_value)
                                for new_range_value in function_range_dict:
                                    if new_range_value not in new_range_list:
                                        new_range_list.append(new_range_value)
                                function_values["range"] = new_range_list
                                function.values = json.dumps(function_values)

    @staticmethod
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

    @staticmethod
    def _remove_status_that_are_local_strategy_aliases(device: XTDevice):
        for local_strategy in device.local_strategy.values():
            code = local_strategy.get("status_code")
            if code is None:
                continue
            if aliases := local_strategy.get("status_code_alias", None):
                for alias in aliases:
                    poped_value = None
                    if alias in device.status:
                        poped_value = device.status.pop(alias)
                        if (
                            alias in device.status_range
                            and code not in device.status_range
                        ):
                            device.status_range[code] = device.status_range[alias]
                            device.status_range[code].code = code
                            device.status_range.pop(alias)
                        if alias in device.function and code not in device.function:
                            device.function[code] = device.function[alias]
                            device.function[code].code = code
                            device.function.pop(alias)
                        if poped_value is not None and code not in device.status:
                            device.status[code] = poped_value
