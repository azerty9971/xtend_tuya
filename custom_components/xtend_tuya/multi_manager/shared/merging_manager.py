from __future__ import annotations

import json

from .device import (
    XTDevice,
    XTDeviceStatusRange,
    XTDeviceFunction,
)
from .cloud_fix import (
    CloudFixes,
)

from ...const import (
    LOGGER,  # noqa: F401
)

class XTMergingManager:
    def merge_devices(device1: XTDevice, device2: XTDevice):
        CloudFixes.apply_fixes(device1)
        CloudFixes.apply_fixes(device2)
        XTMergingManager._align_api_usage(device1, device2)
        msg_queue: list[str] = []
        device1.status_range = XTMergingManager.smart_merge(device1.status_range, device2.status_range, msg_queue)
        device1.function = XTMergingManager.smart_merge(device1.function, device2.function, msg_queue)
        device1.status = XTMergingManager.smart_merge(device1.status, device2.status, msg_queue)
        device1.local_strategy = XTMergingManager.smart_merge(device1.local_strategy, device2.local_strategy, msg_queue)
        if msg_queue:
            LOGGER.warning(f"Messages for merging of {device1} and {device2}:")
            for msg in msg_queue:
                LOGGER.warning(msg)
        #XTMergingManager._merge_status(device1, device2)
        #XTMergingManager._merge_function(device1, device2)
        #XTMergingManager._merge_status_range(device1, device2)
        #XTMergingManager._merge_local_strategy(device1, device2)

        #Now link the references so that they point to the same structure in memory
        device2.status_range = device1.status_range
        device2.function = device1.function
        device2.status = device1.status
        device2.local_strategy = device1.local_strategy
        if device1.data_model:
            device2.data_model = device1.data_model
        elif device2.data_model:
            device1.data_model = device2.data_model
        if device1.set_up:
            device2.set_up = device1.set_up
        elif device2.set_up:
            device1.set_up = device2.set_up

    def _align_api_usage(device1: XTDevice, device2: XTDevice):
        for dpId in device1.local_strategy:
            if dpId in device2.local_strategy:
                use_oapi1 = device1.local_strategy[dpId].get("use_open_api")
                use_oapi2 = device2.local_strategy[dpId].get("use_open_api")
                if not use_oapi1 or not use_oapi2:
                    device1.local_strategy[dpId]["use_open_api"] = False
                    device2.local_strategy[dpId]["use_open_api"] = False
                prop_upd1 = device1.local_strategy[dpId].get("property_update")
                prop_upd2 = device2.local_strategy[dpId].get("property_update")
                if not prop_upd1 or not prop_upd2:
                    device1.local_strategy[dpId]["property_update"] = False
                    device2.local_strategy[dpId]["property_update"] = False
    
    def _align_DPTypes(device1: XTDevice, device2: XTDevice):
        for key in device1.status_range:
            if key in device2.status_range:
                match CloudFixes.determine_most_plausible({"type": device1.status_range[key].type}, {"type": device2.status_range[key].type}, "type"):
                    case 1:
                        device2.status_range[key].type = device1.status_range[key].type
                    case 2:
                        device1.status_range[key].type = device2.status_range[key].type
        for key in device1.function:
            if key in device2.function:
                match CloudFixes.determine_most_plausible({"type": device1.function[key].type}, {"type": device2.function[key].type}, "type"):
                    case 1:
                        device2.function[key].type = device1.function[key].type
                    case 2:
                        device1.function[key].type = device2.function[key].type
        for dpId in device1.local_strategy:
            if dpId in device2.local_strategy:
                if config_item1 := device1.local_strategy[dpId].get("config_item"):
                    if "valueType" not in config_item1:
                        continue
                else:
                    continue
                if config_item2 := device2.local_strategy[dpId].get("config_item"):
                    if "valueType" not in config_item2:
                        continue
                else:
                    continue
                match CloudFixes.determine_most_plausible(config_item1, config_item2, "valueType"):
                    case 1:
                        config_item2["valueType"] = config_item1["valueType"]
                    case 2:
                        config_item1["valueType"] = config_item2["valueType"]
                

    def _merge_status(device1: XTDevice, device2: XTDevice):
        XTMergingManager.smart_merge(device1.status, device2.status)

    def _merge_function(device1: XTDevice, device2: XTDevice):
        for function_key in device1.function:
            if function_key in device2.function:
                try:
                    value1 = json.loads(device1.function[function_key].values)
                except Exception:
                    value1 = {}
                try:
                    value2 = json.loads(device2.function[function_key].values)
                except Exception:
                    value2 = {}
                match CloudFixes.determine_most_plausible(value1, value2, "scale"):
                    case None:
                        match CloudFixes.determine_most_plausible(value1, value2, "min"):
                            case None:
                                pass
                            case 1:
                                device2.function[function_key].values = device1.function[function_key].values
                            case 2:
                                device1.function[function_key].values = device2.function[function_key].values
                    case 1:
                        device2.function[function_key].values = device1.function[function_key].values
                    case 2:
                        device1.function[function_key].values = device2.function[function_key].values
                value1 = XTMergingManager.smart_merge(value1, value2)
                
                device1.function[function_key].values = json.dumps(value1)
                device2.function[function_key].values = device1.function[function_key].values
            else:
                device2.function[function_key] = device1.function[function_key]
        for function_key in device2.function:
            if function_key not in device1.function:
                device1.function[function_key] = device2.function[function_key]

    def _merge_status_range(device1: XTDevice, device2: XTDevice):
        for status_range_key in device1.status_range:
            if status_range_key in device2.status_range:
                #determine the most plausible correct status_range
                try:
                    value1 = json.loads(device1.status_range[status_range_key].values)
                except Exception:
                    value1 = {}
                try:
                    value2 = json.loads(device2.status_range[status_range_key].values)
                except Exception:
                    value2 = {}
                match CloudFixes.determine_most_plausible(value1, value2, "scale"):
                    case None:
                        match CloudFixes.determine_most_plausible(value1, value2, "min"):
                            case None:
                                pass
                            case 1:
                                device2.status_range[status_range_key].values = device1.status_range[status_range_key].values
                            case 2:
                                device1.status_range[status_range_key].values = device2.status_range[status_range_key].values
                    case 1:
                        device2.status_range[status_range_key].values = device1.status_range[status_range_key].values
                    case 2:
                        device1.status_range[status_range_key].values = device2.status_range[status_range_key].values
                value1 = XTMergingManager.smart_merge(value1, value2)
                device1.status_range[status_range_key].values = json.dumps(value1)
                device2.status_range[status_range_key].values = device1.status_range[status_range_key].values
            else:
                device2.status_range[status_range_key] = device1.status_range[status_range_key]
        for status_range_key in device2.status_range:
            if status_range_key not in device1.status_range:
                device1.status_range[status_range_key] = device2.status_range[status_range_key]
    
    def _merge_local_strategy(device1: XTDevice, device2: XTDevice):
        for dpId in device1.local_strategy:
            if dpId in device2.local_strategy:
                strategy1 = device1.local_strategy[dpId]
                strategy2 = device2.local_strategy[dpId]

                #Favor as the "main" strategy the one that doesn't use openAPI or Property Update
                st1_prop = strategy1.get("property_update", None)
                st2_prop = strategy2.get("property_update", None)
                st1_oapi = strategy1.get("use_open_api", None)
                st2_oapi = strategy2.get("use_open_api", None)
                if st1_oapi != st2_oapi:
                    if st2_oapi is not None and not st2_oapi:
                        strategy1 = device2.local_strategy[dpId]
                        strategy2 = device1.local_strategy[dpId]
                elif st1_prop != st2_prop:
                    if st2_prop is not None and not st2_prop:
                        strategy1 = device2.local_strategy[dpId]
                        strategy2 = device1.local_strategy[dpId]


                XTMergingManager._copy_if_different(strategy1, strategy2, "value_convert")
                XTMergingManager._copy_if_different(strategy1, strategy2, "status_code", "status_code_alias")
                if "config_item" in strategy1 and "config_item" in strategy2:
                    XTMergingManager._merge_config_item(strategy1["config_item"], strategy2["config_item"])
                elif "config_item" in strategy1:
                    strategy2["config_item"] = strategy1["config_item"]
                else:
                    strategy1["config_item"] = strategy2["config_item"]
                if "property_update" in strategy1:
                    strategy2["property_update"] = strategy1["property_update"]
                else:
                    strategy1["property_update"] = False
                    strategy2["property_update"] = strategy1["property_update"]
                if "use_open_api" in strategy1:
                    strategy2["use_open_api"] = strategy1["use_open_api"]
                else:
                    strategy1["use_open_api"] = False
                    strategy2["use_open_api"] = strategy1["use_open_api"]
                if "access_mode" in strategy1:
                    strategy2["access_mode"] = strategy1["access_mode"]
                elif "access_mode" in strategy2:
                    strategy1["access_mode"] = strategy2["access_mode"]
                else:
                    strategy1["access_mode"] = None
                    strategy2["access_mode"] = strategy1["access_mode"]

            else:
                device2.local_strategy[dpId] = device1.local_strategy[dpId]
        for dpId in device2.local_strategy:
            if dpId not in device1.local_strategy:
                device1.local_strategy[dpId] = device2.local_strategy[dpId]

    def _merge_config_item(conf1: dict, conf2: dict):
        XTMergingManager._merge_json_dict(conf2, conf1, "statusFormat")
        if "valueDesc" in conf1 and "valueDesc" in conf2:
            try:
                value1 = json.loads(conf1["valueDesc"])
            except Exception:
                value1 = {}
            try:
                value2 = json.loads(conf2["valueDesc"])
            except Exception:
                value2 = {}
            match CloudFixes.determine_most_plausible(value1, value2, "scale"):
                case None:
                    match CloudFixes.determine_most_plausible(value1, value2, "min"):
                        case None:
                            pass
                        case 1:
                            conf2["valueDesc"] = conf1["valueDesc"]
                        case 2:
                            conf1["valueDesc"] = conf2["valueDesc"]
                case 1:
                    conf2["valueDesc"] = conf1["valueDesc"]
                case 2:
                    conf1["valueDesc"] = conf2["valueDesc"]
        XTMergingManager._merge_json_dict(conf2, conf1, "valueDesc")
        XTMergingManager._copy_if_different(conf1, conf2, "valueType")
        if "enumMappingMap" in conf1 and "enumMappingMap" in conf2:
            XTMergingManager._merge_dict(conf1["enumMappingMap"], conf2["enumMappingMap"])
        elif "enumMappingMap" in conf1:
            conf2["enumMappingMap"] = conf1["enumMappingMap"]
        elif "enumMappingMap" in conf2:
            conf1["enumMappingMap"] = conf2["enumMappingMap"]
        XTMergingManager._copy_if_different(conf1, conf2, "pid")

    def _copy_if_different(dict1: dict, dict2: dict, key: any, alias_key: any = None):
        is_same, val1, val2 = XTMergingManager._is_dict_entry_the_same(dict1, dict2, key)
        if alias_key is not None:
            if alias_key not in dict1:
                dict1[alias_key] = list()
            if alias_key not in dict2:
                dict2[alias_key] = dict1[alias_key]
        if not is_same:
            dict2[key] = dict1[key]
            if alias_key is not None and val2 is not None:
                dict1[alias_key].append(val2)

    def _merge_json_dict(dict1: dict, dict2: dict, key: any):
        if key not in dict1 or key not in dict2:
            if key in dict1:
                dict2[key] = dict1[key]
            elif key in dict2:
                dict1[key] = dict2[key]
            else:
                dict1[key] = "{}"
                dict2[key] = dict1[key]
            return
        json_dict1 = json.loads(dict1[key])
        json_dict2 = json.loads(dict2[key])
        XTMergingManager._merge_dict(json_dict1, json_dict2)
        dict1[key] = json.dumps(json_dict1)
        dict2[key] = dict1[key]

    def _is_dict_entry_the_same(dict1: dict, dict2: dict, key: any):
        val1 = None
        if key in dict1:
            val1 = dict1[key]
        val2 = None
        if key in dict2:
            val2 = dict2[key]
        
        if val1 == val2:
            return True, val1, val2
        else:
            return False, val1, val2
        

    def _merge_dict(dict1: dict, dict2: dict):
        for key in dict1:
            if key not in dict2:
                dict2[key] = dict1[key]
        for key in dict2:
            if key not in dict1:
                dict1[key] = dict2[key]

    def smart_merge(left: any, right: any, msg_queue: list[str] = []) -> any:
        if left is None or right is None:
            if left is not None:
                return left
            return right
        if type(left) is not type(right):
            msg_queue.append(f"Merging tried to merge objects of different types: {type(left)} and {type(right)}, returning left")
            return left
        if isinstance(left, XTDeviceStatusRange):
            left.code = XTMergingManager.smart_merge(left.code, right.code, msg_queue)
            left.type = XTMergingManager.smart_merge(left.type, right.type, msg_queue)
            left.values = XTMergingManager.smart_merge(left.values, right.values, msg_queue)
            return left
        elif isinstance(left, XTDeviceFunction):
            left.code = XTMergingManager.smart_merge(left.code, right.code, msg_queue)
            left.type = XTMergingManager.smart_merge(left.type, right.type, msg_queue)
            left.desc = XTMergingManager.smart_merge(left.desc, right.desc, msg_queue)
            left.name = XTMergingManager.smart_merge(left.name, right.name, msg_queue)
            left.values = XTMergingManager.smart_merge(left.values, right.values, msg_queue)
            return left
        elif isinstance(left, dict):
            for key in left:
                if key in right:
                    left[key] = XTMergingManager.smart_merge(left[key], right[key], msg_queue)
                    right[key] = left[key]
                else:
                    right[key] = left[key]
            for key in right:
                if key not in left:
                    left[key] = right[key]
            return left
        elif isinstance(left, list):
            for key in left:
                if key not in right:
                    right.append(key)
            for key in right:
                if key not in left:
                    left.append(key)
            return left
        elif isinstance(left, tuple):
            left_list = list(left)
            right_list = list(right)
            return tuple(XTMergingManager.smart_merge(left_list, right_list, msg_queue))
        elif isinstance(left, set):
            return left.update(right)
        elif isinstance(left, str):
            #Strings could be strings or represent a json subtree
            try:
                left_json = json.loads(left)
            except Exception:
                left_json = None
            try:
                right_json = json.loads(right)
            except Exception:
                right_json = None
            if left_json is not None and right_json is not None:
                return json.dumps(XTMergingManager.smart_merge(left_json, right_json, msg_queue))
            elif left_json is not None:
                return json.dumps(left_json)
            elif right_json is not None:
                return json.dumps(right_json)
            else:
                if left != right:
                    msg_queue.append(f"Merging {type(left)} that are different: |{left}| <=> |{right}|, using left")
                return left
        else:
            if left != right:
                msg_queue.append(f"Merging {type(left)} that are different: |{left}| <=> |{right}|, using left")
            return left
    