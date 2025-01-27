from __future__ import annotations

import json
import copy

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
from ..multi_manager import (
    MultiManager,
)

class XTMergingManager:
    def merge_devices(device1: XTDevice, device2: XTDevice, multi_manager: MultiManager = None):
        msg_queue: list[str] = []

        #if multi_manager:
        #    multi_manager.device_watcher.report_message(device1.id, f"About to merge {device1.source}:{device1}\r\n\r\nand\r\n\r\n{device2.source}:{device2}", device1)
        device1_bak = copy.deepcopy(device1)
        device2_bak = copy.deepcopy(device2)
        #Make both devices compliant
        XTMergingManager._fix_incorrect_valuedescr(device1, device2)
        XTMergingManager._fix_incorrect_valuedescr(device2, device1)
        CloudFixes.apply_fixes(device1)
        CloudFixes.apply_fixes(device2)

        #Now decide between each device which on has "the truth" and set it in both
        XTMergingManager._align_device_properties(device1, device2, msg_queue)
        XTMergingManager._align_DPTypes(device1, device2)
        XTMergingManager._align_api_usage(device1, device2)
        XTMergingManager._prefer_non_default_value_convert(device1, device2)
        XTMergingManager._align_valuedescr(device1, device2)

        #Finally, align and extend both devices
        device1.status_range = XTMergingManager.smart_merge(device1.status_range, device2.status_range, msg_queue, "status_range")
        device1.function = XTMergingManager.smart_merge(device1.function, device2.function, msg_queue, "function")
        device1.status = XTMergingManager.smart_merge(device1.status, device2.status, None, "status")
        device1.local_strategy = XTMergingManager.smart_merge(device1.local_strategy, device2.local_strategy, msg_queue, "local_strategy")
        if msg_queue:
            LOGGER.warning(f"Messages for merging of {device1_bak} and {device2_bak}:")
            for msg in msg_queue:
                LOGGER.warning(msg)

        #Now link the references so that they point to the same structure in memory
        device2.status_range = device1.status_range
        device2.function = device1.function
        device2.status = device1.status
        device2.local_strategy = device1.local_strategy
        #if multi_manager:
        #    multi_manager.device_watcher.report_message(device1.id, f"Merged into {device1}", device1)

    def _align_device_properties(device1: XTDevice, device2: XTDevice, msg_queue: list[str] | None = None):
        device1.name            = XTMergingManager.smart_merge(device1.name, device2.name, msg_queue, "device.name")
        device1.local_key       = XTMergingManager.smart_merge(device1.local_key, device2.local_key, msg_queue, "device.local_key")
        device1.category        = XTMergingManager.smart_merge(device1.category, device2.category, msg_queue, "device.category")
        device1.product_id      = XTMergingManager.smart_merge(device1.product_id, device2.product_id, msg_queue, "device.product_id")
        device1.product_name    = XTMergingManager.smart_merge(device1.product_name, device2.product_name, msg_queue, "device.product_name")
        device1.sub             = XTMergingManager.smart_merge(device1.sub, device2.sub, msg_queue, "device.sub")
        device1.uuid            = XTMergingManager.smart_merge(device1.uuid, device2.uuid, msg_queue, "device.uuid")
        device1.asset_id        = XTMergingManager.smart_merge(device1.asset_id, device2.asset_id, msg_queue, "device.asset_id")
        device1.online          = XTMergingManager.smart_merge(device1.online, device2.online, msg_queue, "device.online")
        device1.icon            = XTMergingManager.smart_merge(device1.icon, device2.icon, msg_queue, "device.icon")
        device1.ip              = XTMergingManager.smart_merge(device1.ip, device2.ip, msg_queue, "device.ip")
        device1.time_zone       = XTMergingManager.smart_merge(device1.time_zone, device2.time_zone, msg_queue, "device.time_zone")
        #Differs between API calls (suppress warning)
        if device2.active_time > 0:
            device1.active_time = device2.active_time
        else:
            device2.active_time = device1.active_time
        if device2.create_time > 0:
            device1.create_time = device2.create_time
        else:
            device2.create_time = device1.create_time
        if device2.update_time > 0:
            device1.update_time = device2.update_time
        else:
            device2.update_time = device1.update_time
        if device1.set_up or device2.set_up:
            device1.set_up = True
            device2.set_up = True
        if device1.support_local or device2.support_local:
            device1.support_local = True
            device2.support_local = True
        device1.data_model      = XTMergingManager.smart_merge(device1.data_model, device2.data_model, msg_queue, "device.data_model")

    def _fix_incorrect_valuedescr(device1: XTDevice, device2: XTDevice):
        for code in device1.function:
            if code in device2.function:
                value1_dict, value1_raw = CloudFixes.get_value_descr_dict(device1.function[code].values)
                value2_dict, value2_raw = CloudFixes.get_value_descr_dict(device2.function[code].values)
            else:
                continue
            if value1_dict is None or value2_dict is None:
                if value1_dict is not None:
                    device2.function[code].values = device1.function[code].values
                elif value2_dict is not None:
                    device1.function[code].values = device2.function[code].values
                else:
                    device1.function[code].values = CloudFixes.get_fixed_value_descr(value1_raw, value2_raw)
                    device2.function[code].values = device1.function[code].values
        
        for code in device1.status_range:
            if code in device2.status_range:
                value1_dict, value1_raw = CloudFixes.get_value_descr_dict(device1.status_range[code].values)
                value2_dict, value2_raw = CloudFixes.get_value_descr_dict(device2.status_range[code].values)
            else:
                continue
            if value1_dict is None or value2_dict is None:
                if value1_dict is not None:
                    device2.status_range[code].values = device1.status_range[code].values
                elif value2_dict is not None:
                    device1.status_range[code].values = device2.status_range[code].values
                else:
                    device1.status_range[code].values = CloudFixes.get_fixed_value_descr(value1_raw, value2_raw)
                    device2.status_range[code].values = device1.status_range[code].values
        
        for dpId in device1.local_strategy:
            value1_dict = None
            value1_raw = None
            value2_dict = None
            value2_raw = None
            if dpId in device2.local_strategy:
                if config_item1 := device1.local_strategy[dpId].get("config_item"):
                    value1_dict, value1_raw = CloudFixes.get_value_descr_dict(config_item1.get("valueDesc"))
                if config_item2 := device2.local_strategy[dpId].get("config_item"):
                    value2_dict, value2_raw = CloudFixes.get_value_descr_dict(config_item2.get("valueDesc"))
            else:
                continue
            if value1_raw is not None or value2_raw is not None:
                #At least one local strategy has a value descriptor
                if value1_dict is None or value2_dict is None:
                    if value1_dict is not None:
                        config_item2["valueDesc"] = config_item1["valueDesc"]
                    elif value2_dict is not None:
                        config_item1["valueDesc"] = config_item2["valueDesc"]
                    else:
                        config_item1["valueDesc"] = CloudFixes.get_fixed_value_descr(value1_raw, value2_raw)
                        config_item2["valueDesc"] = config_item1["valueDesc"]

    def _align_valuedescr(device1: XTDevice, device2: XTDevice):
        for code in device1.status_range:
            if code in device2.status_range and device1.status_range[code].values != device2.status_range[code].values:
                value1 = json.loads(device1.status_range[code].values)
                value2 = json.loads(device2.status_range[code].values)
                computed_diff = CloudFixes.compute_aligned_valuedescr(value1, value2, None)
                for fix_code in computed_diff:
                    value1[fix_code] = computed_diff[fix_code]
                    value2[fix_code] = computed_diff[fix_code]
                device1.status_range[code].values = json.dumps(value1)
                device2.status_range[code].values = json.dumps(value2)
        for code in device1.function:
            if code in device2.function and device1.function[code].values != device2.function[code].values:
                value1 = json.loads(device1.function[code].values)
                value2 = json.loads(device2.function[code].values)
                computed_diff = CloudFixes.compute_aligned_valuedescr(value1, value2, None)
                for fix_code in computed_diff:
                    value1[fix_code] = computed_diff[fix_code]
                    value2[fix_code] = computed_diff[fix_code]
                device1.function[code].values = json.dumps(value1)
                device2.function[code].values = json.dumps(value2)
        for dp_id in device1.local_strategy:
            if dp_id in device2.local_strategy:
                config_item1 = device1.local_strategy[dp_id].get("config_item")
                config_item2 = device2.local_strategy[dp_id].get("config_item")
                if config_item1 is not None and config_item2 is not None:
                    value_descr1 = config_item1.get("valueDesc")
                    value_descr2 = config_item2.get("valueDesc")
                    if value_descr1 is not None and value_descr2 is not None:
                        value1 = json.loads(value_descr1)
                        value2 = json.loads(value_descr2)
                        computed_diff = CloudFixes.compute_aligned_valuedescr(value1, value2, None)
                        for fix_code in computed_diff:
                            value1[fix_code] = computed_diff[fix_code]
                            value2[fix_code] = computed_diff[fix_code]
                        config_item1["valueDesc"] = json.dumps(value1)
                        config_item2["valueDesc"] = json.dumps(value2)

    def _align_api_usage(device1: XTDevice, device2: XTDevice):
        for dpId in device1.local_strategy:
            if dpId in device2.local_strategy:
                use_oapi1 = device1.local_strategy[dpId].get("use_open_api")
                use_oapi2 = device2.local_strategy[dpId].get("use_open_api")
                prop_upd1 = device1.local_strategy[dpId].get("property_update")
                prop_upd2 = device2.local_strategy[dpId].get("property_update")
                prefer = None
                if not use_oapi1:
                    prefer = 1
                elif not use_oapi2:
                    prefer = 2
                elif not prop_upd1:
                    prefer = 1
                elif not prop_upd2:
                    prefer = 2

                match prefer:
                    case 1:
                        device2.local_strategy[dpId]["use_open_api"] = device1.local_strategy[dpId]["use_open_api"]
                        device2.local_strategy[dpId]["property_update"] = device1.local_strategy[dpId]["property_update"]
                        device2.local_strategy[dpId]["status_code"] = device1.local_strategy[dpId]["status_code"]
                    case 2:
                        device1.local_strategy[dpId]["use_open_api"] = device2.local_strategy[dpId]["use_open_api"]
                        device1.local_strategy[dpId]["property_update"] = device2.local_strategy[dpId]["property_update"]
                        device1.local_strategy[dpId]["status_code"] = device2.local_strategy[dpId]["status_code"]
    
    def _align_DPTypes(device1: XTDevice, device2: XTDevice):
        for key in device1.status_range:
            if key in device2.status_range:
                state_value = device1.status.get(key)
                if state_value is None:
                    state_value = device2.status.get(key)
                match CloudFixes.determine_most_plausible({"type": device1.status_range[key].type}, {"type": device2.status_range[key].type}, "type", state_value):
                    case 1:
                        device2.status_range[key].type = device1.status_range[key].type
                        device2.status_range[key].values = device1.status_range[key].values
                    case 2:
                        device1.status_range[key].type = device2.status_range[key].type
                        device1.status_range[key].values = device2.status_range[key].values
        for key in device1.function:
            if key in device2.function:
                state_value = device1.status.get(key)
                if state_value is None:
                    state_value = device2.status.get(key)
                match CloudFixes.determine_most_plausible({"type": device1.function[key].type}, {"type": device2.function[key].type}, "type", state_value):
                    case 1:
                        device2.function[key].type = device1.function[key].type
                        device2.function[key].values = device1.function[key].values
                    case 2:
                        device1.function[key].type = device2.function[key].type
                        device1.function[key].values = device2.function[key].values
        for dpId in device1.local_strategy:
            if dpId in device2.local_strategy:
                state_value = None
                if code := device1.local_strategy[dpId].get("status_code"):
                    state_value = device1.status.get(code)
                    if state_value is None:
                        state_value = device2.status.get(code)
                if state_value is None:
                    if code := device2.local_strategy[dpId].get("status_code"):
                        state_value = device1.status.get(code)
                        if state_value is None:
                            state_value = device2.status.get(code)
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
                match CloudFixes.determine_most_plausible(config_item1, config_item2, "valueType", state_value):
                    case 1:
                        config_item2["valueType"] = config_item1["valueType"]
                        config_item2["valueDesc"] = config_item1["valueDesc"]
                    case 2:
                        config_item1["valueType"] = config_item2["valueType"]
                        config_item1["valueDesc"] = config_item2["valueDesc"]
    
    def _prefer_non_default_value_convert(device1: XTDevice, device2: XTDevice):
        for dpId in device1.local_strategy:
            if dpId in device2.local_strategy:
                valConv1 = device1.local_strategy[dpId].get("value_convert")
                valConv2 = device2.local_strategy[dpId].get("value_convert")
                if valConv1 != valConv2:
                    if valConv1 == "default" or valConv1 is None:
                        device1.local_strategy[dpId]["value_convert"] = device2.local_strategy[dpId]["value_convert"]
                    else:
                        device2.local_strategy[dpId]["value_convert"] = device1.local_strategy[dpId]["value_convert"]

    def smart_merge(left: any, right: any, msg_queue: list[str] | None = None, path: str = "") -> any:
        if left is None or right is None:
            if left is not None:
                return left
            return right
        if (
            type(left) is not type(right) 
            and not (isinstance(left, str) and isinstance(right, str)) #Used to prevent warning on classes that represent a string (DPType and TuyaDPType)
            ):
            if msg_queue is not None:
                msg_queue.append(f"Merging tried to merge objects of different types: {type(left)} and {type(right)}, returning left ({path})")
            return left
        if isinstance(left, XTDeviceStatusRange):
            left.code = XTMergingManager.smart_merge(left.code, right.code, msg_queue, f"{path}.code")
            left.type = XTMergingManager.smart_merge(left.type, right.type, msg_queue, f"{path}.type")
            left.values = XTMergingManager.smart_merge(left.values, right.values, msg_queue, f"{path}.values")
            left.dp_id = XTMergingManager.smart_merge(left.dp_id, right.dp_id, msg_queue, f"{path}.dp_id")
            return left
        elif isinstance(left, XTDeviceFunction):
            left.code = XTMergingManager.smart_merge(left.code, right.code, msg_queue, f"{path}.code")
            left.type = XTMergingManager.smart_merge(left.type, right.type, msg_queue, f"{path}.type")
            left.desc = XTMergingManager.smart_merge(left.desc, right.desc, msg_queue, f"{path}.desc")
            left.name = XTMergingManager.smart_merge(left.name, right.name, msg_queue, f"{path}.name")
            left.values = XTMergingManager.smart_merge(left.values, right.values, msg_queue, f"{path}.values")
            left.dp_id = XTMergingManager.smart_merge(left.dp_id, right.dp_id, msg_queue, f"{path}.dp_id")
            return left
        elif isinstance(left, dict):
            for key in left:
                if key in right:
                    left[key] = XTMergingManager.smart_merge(left[key], right[key], msg_queue, f"{path}[{key}]")
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
                return json.dumps(XTMergingManager.smart_merge(left_json, right_json, msg_queue, f"{path}.@JS@"))
            elif left_json is not None:
                return json.dumps(left_json)
            elif right_json is not None:
                return json.dumps(right_json)
            elif right == "":
                return left
            elif left == "":
                return right
            else:
                if left != right and msg_queue is not None:
                    msg_queue.append(f"Merging {type(left)} that are different: |{left}| <=> |{right}|, using left ({path})")
                return left
        else:
            if left != right and msg_queue is not None:
                msg_queue.append(f"Merging {type(left)} that are different: |{left}| <=> |{right}|, using left ({path})")
            return left
    