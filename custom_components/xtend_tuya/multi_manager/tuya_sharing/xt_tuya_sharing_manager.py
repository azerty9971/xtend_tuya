"""
This file contains all the code that inherit from Tuya integration
"""

from __future__ import annotations
from typing import Any

from tuya_sharing.manager import (
    Manager,
    SceneRepository,
    UserRepository,
)

from tuya_sharing.home import (
    SmartLifeHome,
    HomeRepository,
)

from .import_stub import (
    XTSharingDeviceManager,
)

from ...const import (
    LOGGER,  # noqa: F401
    MESSAGE_SOURCE_TUYA_SHARING,
)

from ..multi_manager import (
    MultiManager,
)
from ..shared.device import (
    XTDevice,
)

from .xt_tuya_sharing_device_repository import (
    XTSharingDeviceRepository
)

class XTSharingDeviceManager(Manager):  # noqa: F811
    def __init__(
        self,
        multi_manager: MultiManager,
        other_device_manager: Manager = None
    ) -> None:
        self.multi_manager = multi_manager
        self.terminal_id = None
        self.mq = None
        self.customer_api = None
        self.home_repository: HomeRepository = None
        self.device_repository: XTSharingDeviceRepository = None
        self.scene_repository: SceneRepository = None
        self.user_repository: UserRepository = None
        self.device_map: dict[str, XTDevice] = {}
        self.user_homes: list[SmartLifeHome] = []
        self.device_listeners = set()
        self.other_device_manager = other_device_manager
        self.reuse_config = False
    
    def forward_message_to_multi_manager(self, msg:str):
        self.multi_manager.on_message(MESSAGE_SOURCE_TUYA_SHARING, msg)

    def on_external_refresh_mq(self):
        if self.other_device_manager is not None:
            self.mq = self.other_device_manager.mq
            self.mq.add_message_listener(self.forward_message_to_multi_manager)
            self.mq.remove_message_listener(self.other_device_manager.on_message)

    def refresh_mq(self):
        if self.other_device_manager is not None:
            if self.mq and self.mq != self.other_device_manager.mq:
                self.mq.stop()
            self.other_device_manager.refresh_mq()
            return
        super().refresh_mq()
        self.mq.add_message_listener(self.forward_message_to_multi_manager)
        self.mq.remove_message_listener(self.on_message)

    def set_overriden_device_manager(self, other_device_manager: Manager) -> None:
        self.other_device_manager = other_device_manager
    
    def get_overriden_device_manager(self) -> Manager | None:
        return self.other_device_manager
    
    def copy_statuses_to_tuya(self, device: XTDevice) -> bool:
        added_new_statuses: bool = False
        if other_manager := self.get_overriden_device_manager():
            if device.id in other_manager.device_map:
                self.multi_manager.device_watcher.report_message(device.id, f"BEFORE copy_statuses_to_tuya: {other_manager.device_map[device.id].status}", device)
                for code in device.status:
                    if code not in other_manager.device_map[device.id].status:
                        added_new_statuses = True
                    other_manager.device_map[device.id].status[code] = device.status[code]
                self.multi_manager.device_watcher.report_message(device.id, f"AFTER copy_statuses_to_tuya: {other_manager.device_map[device.id].status}", device)
        return added_new_statuses

    def _on_device_report(self, device_id: str, status: list):
        device = self.device_map.get(device_id, None)
        if not device:
            return
        status_new = self.multi_manager.convert_device_report_status_list(device_id, status)
        self.multi_manager.device_watcher.report_message(f"device report {MESSAGE_SOURCE_TUYA_SHARING}: {status_new}")
        status_new = self.multi_manager.multi_source_handler.filter_status_list(device_id, MESSAGE_SOURCE_TUYA_SHARING, status_new)
        status_new = self.multi_manager.virtual_state_handler.apply_virtual_states_to_status_list(device, status_new)

        super()._on_device_report(device_id, status_new)
    
    def send_commands(
            self, device_id: str, commands: list[dict[str, Any]]
    ):
        if other_manager := self.get_overriden_device_manager():
            other_manager.send_commands(device_id, commands)
            return
        super().send_commands(device_id, commands)
    
    def send_lock_unlock_command(
            self, device_id: str, lock: bool
    ) -> bool:
        supported_unlock_types: list[str] = []
        if lock:
            open = "false"
        else:
            open = "true"

        remote_unlock_types = self.customer_api.get(f"/v1.0/devices/{device_id}/door-lock/remote-unlocks")
        LOGGER.warning(f"1: {remote_unlock_types}")
        if remote_unlock_types.get("success", False):
            results = remote_unlock_types.get("result", [])
            for result in results:
                if result.get("open", False):
                    if supported_unlock_type := result.get("remote_unlock_type", None):
                        supported_unlock_types.append(supported_unlock_type)
        if "remoteUnlockWithoutPwd" in supported_unlock_types:
            ticket = self.customer_api.post(f"/v1.0/devices/{device_id}/door-lock/password-ticket")
            LOGGER.warning(f"2: {ticket}")
            if ticket.get("success", False):
                result = ticket.get("result", {})
                if ticket_id := result.get("ticket_id", None):
                    lock_operation = self.customer_api.post(f"/v1.0/smart-lock/devices/{device_id}/password-free/door-operate", {"ticket_id": ticket_id, "open": open})
                    LOGGER.warning(f"3: {lock_operation}")
                    return lock_operation.get("success", False)
        return False