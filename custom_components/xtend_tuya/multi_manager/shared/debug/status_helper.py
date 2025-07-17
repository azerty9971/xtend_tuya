from __future__ import annotations
import custom_components.xtend_tuya.multi_manager.multi_manager as mm


class StatusHelper:
    def __init__(self, multi_manager: mm.MultiManager):
        self.multi_manager = multi_manager

    def is_status_in_status_list(
        self, device_id: str, status: str, status_list: list
    ) -> bool:
        for item in status_list:
            code, dpId, new_key_value, result_ok = (
                self.multi_manager._read_code_dpid_value_from_state(
                    device_id, item, False, True
                )
            )
            if result_ok and code == status:
                return True
        return False
