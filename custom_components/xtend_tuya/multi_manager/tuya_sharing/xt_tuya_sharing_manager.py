"""
This file contains all the code that inherit from Tuya integration
"""

from __future__ import annotations
from typing import Any

from tuya_sharing.manager import (
    Manager,
    SceneRepository,
    UserRepository,
    CustomerApi,
    BIZCODE_OFFLINE,
    BIZCODE_ONLINE,
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
from .xt_tuya_sharing_mq import (
    XTSharingMQ,
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
        self.customer_api: CustomerApi = None
        self.home_repository: HomeRepository = None
        self.device_repository: XTSharingDeviceRepository = None
        self.scene_repository: SceneRepository = None
        self.user_repository: UserRepository = None
        self.device_map: dict[str, XTDevice] = {}
        self.user_homes: list[SmartLifeHome] = []
        self.device_listeners = set()
        self.other_device_manager = other_device_manager
    
    @property
    def reuse_config(self) -> bool:
        if self.other_device_manager:
            return True
        return False

    def forward_message_to_multi_manager(self, msg:str):
        self.multi_manager.on_message(MESSAGE_SOURCE_TUYA_SHARING, msg)

    def on_external_refresh_mq(self):
        if self.other_device_manager is not None:
            self.mq = self.other_device_manager.mq
            self.mq.add_message_listener(self.forward_message_to_multi_manager)
            self.mq.remove_message_listener(self.other_device_manager.on_message)

    def refresh_mq(self):
        if self.other_device_manager:
            if self.mq and self.mq != self.other_device_manager.mq:
                self.mq.stop()
            self.other_device_manager.refresh_mq()
            return
        if self.mq is not None:
            self.mq.stop()
            self.mq = None

        home_ids = [home.id for home in self.user_homes]
        device = [device for device in self.device_map.values() if
                  hasattr(device, "id") and getattr(device, "set_up", False)]

        self.mq = XTSharingMQ(self.customer_api, home_ids, device)
        self.mq.start()
        self.mq.add_message_listener(self.forward_message_to_multi_manager)

    def set_overriden_device_manager(self, other_device_manager: Manager) -> None:
        self.other_device_manager = other_device_manager
    
    def get_overriden_device_manager(self) -> Manager | None:
        return self.other_device_manager
    
    def copy_statuses_to_tuya(self, device: XTDevice) -> bool:
        added_new_statuses: bool = False
        if other_manager := self.get_overriden_device_manager():
            if device.id in other_manager.device_map:
                #self.multi_manager.device_watcher.report_message(device.id, f"BEFORE copy_statuses_to_tuya: {other_manager.device_map[device.id].status}", device)
                for code in device.status:
                    if code not in other_manager.device_map[device.id].status:
                        added_new_statuses = True
                    other_manager.device_map[device.id].status[code] = device.status[code]
                #self.multi_manager.device_watcher.report_message(device.id, f"AFTER copy_statuses_to_tuya: {other_manager.device_map[device.id].status}", device)
        return added_new_statuses

    def update_device_cache(self):
        super().update_device_cache()
        
        for device in self.multi_manager.devices_shared.values():
            if device.id not in self.device_map:
                new_device = device.get_copy()
                self.device_repository.update_device_strategy_info(new_device)
                self.device_map[device.id] = new_device

    def _on_device_other(self, device_id: str, biz_code: str, data: dict[str, Any]):
        self.multi_manager.device_watcher.report_message(device_id, f"[{MESSAGE_SOURCE_TUYA_SHARING}]On device other: {biz_code} <=> {data}")
        super()._on_device_other(device_id, biz_code, data)
        if biz_code in [BIZCODE_ONLINE, BIZCODE_OFFLINE]:
            self.multi_manager.update_device_online_status(device_id)

    def _on_device_report(self, device_id: str, status: list):
        device = self.device_map.get(device_id, None)
        if not device:
            return
        status_new = self.multi_manager.convert_device_report_status_list(device_id, status)
        status_new = self.multi_manager.multi_source_handler.filter_status_list(device_id, MESSAGE_SOURCE_TUYA_SHARING, status_new)
        status_new = self.multi_manager.virtual_state_handler.apply_virtual_states_to_status_list(device, status_new, MESSAGE_SOURCE_TUYA_SHARING)

        super()._on_device_report(device_id, status_new)
            
    def send_commands(
            self, device_id: str, commands: list[dict[str, Any]]
    ):
        self.multi_manager.device_watcher.report_message(device_id, f"Sending Tuya commands: {commands}")
        if other_manager := self.get_overriden_device_manager():
            other_manager.send_commands(device_id, commands)
            return
        super().send_commands(device_id, commands)
    
    def send_lock_unlock_command(
            self, device_id: str, lock: bool
    ) -> bool:
        #I didn't find a way to implement this using the Sharing SDK...
        return False