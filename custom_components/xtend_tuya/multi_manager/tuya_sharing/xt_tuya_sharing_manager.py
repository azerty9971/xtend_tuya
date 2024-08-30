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
from tuya_sharing.device import (
    CustomerDevice,
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
        self.device_map: dict[str, CustomerDevice] = {}
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
        if self.other_device_manager is not None:
            return self.other_device_manager
        return None
    
    def _on_device_report(self, device_id: str, status: list):
        device = self.device_map.get(device_id, None)
        if not device:
            return
        status_new = self.multi_manager.convert_device_report_status_list(device_id, status)
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