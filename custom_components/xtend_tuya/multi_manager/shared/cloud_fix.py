from __future__ import annotations

import json

from .device import (
    XTDevice,
)

class CloudFixes:
    def apply_fixes(device: XTDevice):
        CloudFixes._fix_missing_local_strategy_enum_mapping_map(device)
        CloudFixes._fix_missing_aliases_using_status_format(device)
        CloudFixes._remove_status_that_are_local_strategy_aliases(device)

    def _fix_missing_local_strategy_enum_mapping_map(device: XTDevice):
        for local_strategy in device.local_strategy.values():
            if config_item := local_strategy.get("config_item", None):
                if mappings := config_item.get("enumMappingMap", None):
                    if 'false' in mappings and str(False) not in mappings:
                        mappings[str(False)] = mappings['false']
                    if 'true' in mappings and str(True) not in mappings:
                        mappings[str(True)] = mappings['true']
    
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