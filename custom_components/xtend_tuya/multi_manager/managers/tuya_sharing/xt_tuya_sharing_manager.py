"""
This file contains all the code that inherit from Tuya integration
"""

from __future__ import annotations
from typing import Any, cast
import json
from tuya_sharing.manager import (
    Manager,
    SceneRepository,
    UserRepository,
    PROTOCOL_DEVICE_REPORT,
    PROTOCOL_OTHER,
    BIZCODE_ONLINE,
    BIZCODE_OFFLINE,
    BIZCODE_NAME_UPDATE,
    BIZCODE_DPNAME_UPDATE,
    BIZCODE_BIND_USER,
    BIZCODE_DELETE,
)
from tuya_sharing.home import (
    SmartLifeHome,
    HomeRepository,
)
from .xt_tuya_sharing_api import (
    XTSharingAPI,
)
from ....const import (
    MESSAGE_SOURCE_TUYA_SHARING,
    XTDeviceSourcePriority,
    XTLockingMechanism,
    LOGGER,  # noqa: F401
    XTDeviceWatcherCategory,
    BIZCODE_EVENT_NOTIFY,
    XT_DEVICE_EVENT_NOTIFY_DPCODE,
)
from ...multi_manager import (
    MultiManager,
)
from ...shared.shared_classes import (
    XTDevice,
    XTDeviceMap,
)
import custom_components.xtend_tuya.multi_manager.managers.tuya_sharing.xt_tuya_sharing_device_repository as dr
import custom_components.xtend_tuya.multi_manager.managers.tuya_sharing.xt_tuya_sharing_mq as mq


class XTSharingDeviceManager(Manager):  # noqa: F811
    def __init__(
        self, multi_manager: MultiManager, other_device_manager: Manager | None = None
    ) -> None:
        super().__init__(
            client_id="", user_code="", terminal_id="", end_point="", token_response={}
        )
        self.multi_manager = multi_manager
        self.terminal_id: str | None = None
        self.mq: mq.SharingMQ | None = None
        self.customer_api: XTSharingAPI | None = None
        self.home_repository: HomeRepository | None = None
        self.device_repository: dr.XTSharingDeviceRepository | None = None
        self.scene_repository: SceneRepository | None = None
        self.user_repository: UserRepository | None = None
        self.device_map: XTDeviceMap = XTDeviceMap(  # type: ignore
            {}, XTDeviceSourcePriority.TUYA_SHARED
        )
        self.user_homes: list[SmartLifeHome] = []
        self.device_listeners = set()
        self.__other_device_manager: Manager | None = None
        self.__overriden_device_map: XTDeviceMap | None = None
        self.set_overriden_device_manager(other_device_manager)

    @property
    def reuse_config(self) -> bool:
        if self.__other_device_manager:
            return True
        return False

    def forward_message_to_multi_manager(self, msg: dict):
        self.multi_manager.on_message(msg, MESSAGE_SOURCE_TUYA_SHARING)

    def on_external_refresh_mq(self):
        if self.__other_device_manager is not None:
            self.mq = self.__other_device_manager.mq
            if self.mq is not None:
                self.mq.add_message_listener(self.forward_message_to_multi_manager)
                self.mq.remove_message_listener(self.__other_device_manager.on_message)

    def refresh_mq(self):
        if self.__other_device_manager:
            if self.mq and self.mq != self.__other_device_manager.mq:
                self.mq.stop()
            self.__other_device_manager.refresh_mq()
            return
        if self.mq is not None:
            self.mq.stop()
            self.mq = None

        home_ids = [home.id for home in self.user_homes]
        device = [
            device
            for device in self.device_map.values()
            # if hasattr(device, "id") and getattr(device, "set_up", False)
        ]

        if self.customer_api is not None:
            self.mq = mq.XTSharingMQ(
                self.customer_api,
                home_ids,
                device,
                self,
            )
            self.mq.start()
            self.mq.add_message_listener(self.forward_message_to_multi_manager)

    def set_overriden_device_manager(
        self, other_device_manager: Manager | None
    ) -> None:
        self.__other_device_manager = other_device_manager
        if self.__other_device_manager:
            new_device_map: XTDeviceMap = XTDeviceMap(
                {}, XTDeviceSourcePriority.REGULAR_TUYA
            )
            for device in self.__other_device_manager.device_map.values():
                self.multi_manager.device_watcher.report_message(
                    device.id,
                    f"Overriden device from regular Tuya: {device}",
                    XTDeviceWatcherCategory.SHARING_API_INTERNAL,
                    device=device,  # type: ignore
                )
                new_device_map[device.id] = XTDevice.from_compatible_device(
                    device, "RT", XTDeviceSourcePriority.REGULAR_TUYA, True
                )
            self.__overriden_device_map = XTDeviceMap(
                new_device_map, XTDeviceSourcePriority.REGULAR_TUYA
            )

    def get_overriden_device_manager(self) -> Manager | None:
        return self.__other_device_manager

    def get_overriden_device_map(self) -> XTDeviceMap | None:
        return self.__overriden_device_map

    def copy_statuses_to_tuya(self, device: XTDevice) -> bool:
        added_new_statuses: bool = False
        if other_manager := self.get_overriden_device_manager():
            if device.id in other_manager.device_map:
                # self.multi_manager.device_watcher.report_message(device.id, f"BEFORE copy_statuses_to_tuya: {other_manager.device_map[device.id].status}", device)
                for code in device.status:
                    if code not in other_manager.device_map[device.id].status:
                        added_new_statuses = True
                    other_manager.device_map[device.id].status[code] = device.status[
                        code
                    ]
                # self.multi_manager.device_watcher.report_message(device.id, f"AFTER copy_statuses_to_tuya: {other_manager.device_map[device.id].status}", device)
        return added_new_statuses

    def update_device_cache(self):
        super().update_device_cache()

        if self.device_repository is None:
            return None

        for device in self.multi_manager.devices_shared.values():
            if device.id not in self.device_map:
                new_device = device.get_copy()
                self.device_repository.update_device_strategy_info(new_device)
                self.device_map[device.id] = new_device
    
    def delete_home(self, home_id: str):
        index = 0
        for home in self.user_homes:
            if home.id == home_id:
                del self.user_homes[index]
                return None
            index += 1

    def on_message(self, msg: dict[str, Any]):
        try:
            protocol = msg.get("protocol", 0)
            data: dict[str, Any] = msg.get("data", {})

            if protocol == PROTOCOL_DEVICE_REPORT:
                self._on_device_report(data["devId"], data["status"])
            if protocol == PROTOCOL_OTHER and data.get("bizCode") is not None:
                bizcode: str = cast(str, data.get("bizCode"))
                dev_id: str | None = data.get("bizData", {}).get("devId")
                if dev_id is not None:
                    self._on_device_other(dev_id, bizcode, data)
        except Exception as e:
            LOGGER.error(f"on message error {msg=}")
            LOGGER.exception(e)

    def add_device_by_id(self, device_id: str):
        device_ids = [device_id]

        self._update_device_list_info_cache(device_ids)

        if device_id in self.device_map.keys():
            device = self.device_map.get(device_id)
            if device is not None and self.mq is not None:
                self.mq.subscribe_device(device_id, device)
                for listener in self.device_listeners:
                    listener.add_device(device)

    def _on_device_other(self, device_id: str, biz_code: str, data: dict[str, Any]):
        self.multi_manager.device_watcher.report_message(
            device_id,
            f"[{MESSAGE_SOURCE_TUYA_SHARING}]On device other: {biz_code=} {data=}",
            XTDeviceWatcherCategory.MQTT,
        )
        if biz_code not in [
            BIZCODE_ONLINE,
            BIZCODE_OFFLINE,
            BIZCODE_NAME_UPDATE,
            BIZCODE_DPNAME_UPDATE,
            BIZCODE_BIND_USER,
            BIZCODE_DELETE,
            BIZCODE_EVENT_NOTIFY,
        ]:
            LOGGER.warning(
                f"Received unknown BizCode type: {biz_code} with data {data}, please report this to the developer"
            )
        if biz_code == BIZCODE_BIND_USER:
            self.multi_manager.add_device_by_id(device_id)
        elif biz_code == BIZCODE_EVENT_NOTIFY:
            data_value: dict[str, Any] = {}
            biz_data: dict[str, Any] = data.get("bizData", {})
            if event_type := biz_data.get("etype"):
                data_value["event_type"] = event_type
            if event_data := biz_data.get("edata"):
                data_value["event_data"] = event_data
            if event_time := data.get("ts"):
                data_value["event_time"] = event_time
            if data_value and event_time is not None:
                self.multi_manager.on_message(
                    msg={
                        "protocol": PROTOCOL_DEVICE_REPORT,
                        "data": {
                            "devId": device_id,
                            "status": [
                                {
                                    "code": str(XT_DEVICE_EVENT_NOTIFY_DPCODE),
                                    "t": event_time,
                                    "value": json.dumps(data_value),
                                }
                            ],
                        },
                        "t": event_time,
                    },
                    source=MESSAGE_SOURCE_TUYA_SHARING,
                )
        else:
            super()._on_device_other(device_id, biz_code, data)
        if biz_code in [BIZCODE_ONLINE, BIZCODE_OFFLINE]:
            self.multi_manager.update_device_online_status(device_id)

    def _on_device_report(self, device_id: str, status: list):
        self.multi_manager.device_watcher.report_message(
            device_id,
            f"[{MESSAGE_SOURCE_TUYA_SHARING}]On device report: {status=}",
            XTDeviceWatcherCategory.MQTT,
        )
        device = self.device_map.get(device_id, None) or self.multi_manager.device_map.get(device_id, None)
        if not device:
            return
        status_new = self.multi_manager.convert_device_report_status_list(
            device_id,
            status,
            MESSAGE_SOURCE_TUYA_SHARING,
        )
        status_new = self.multi_manager.multi_source_handler.filter_status_list(
            device_id, MESSAGE_SOURCE_TUYA_SHARING, status_new
        )
        status_new = self.multi_manager.virtual_state_handler.apply_virtual_states_to_status_list(
            device, status_new, MESSAGE_SOURCE_TUYA_SHARING
        )

        self._on_device_report_tuya_sharing(device_id, status_new)
    
    def _on_device_report_tuya_sharing(self, device_id: str, status: list[dict[str, Any]]):
        device = self.device_map.get(device_id, None) or self.multi_manager.device_map.get(device_id, None)
        if not device:
            return
        updated_status_properties = []
        dp_timestamps = {}
        value = None
        if device.support_local:
            for item in status:
                # [{'dpId': 1, 't': 1752456620499, 'value': 120}]
                if "dpId" in item and "value" in item:
                    if item["dpId"] not in device.local_strategy:
                        LOGGER.warning(f"mq _on_device_report unknown dpId: {item['dpId']} for {device.id}, local_strategy keys: {list(device.local_strategy.keys())}")
                        continue
                    #CHANGED
                    # dp_id_item = device.local_strategy[item["dpId"]]
                    # strategy_name = dp_id_item["value_convert"]
                    # config_item = dp_id_item["config_item"]
                    # dp_item = (dp_id_item["status_code"], item["value"])
                    # LOGGER.debug(
                    #     f"mq _on_device_report before strategy convert strategy_name={strategy_name},dp_item={dp_item},config_item={config_item}")
                    # code, value = strategy.convert(strategy_name, dp_item, config_item)
                    #END CHANGED
                    #ADDED
                    dp_id_item = device.local_strategy.get(item["dpId"], {})
                    code = dp_id_item.get("status_code")
                    value = item.get("value")
                    if code is None:
                        LOGGER.warning(f"Could not read DPCode for {item} of {device.name}, skipping")
                        continue
                    value = device.apply_dpcode_strategy(code, value, self.multi_manager)
                    #END ADDED

                    status_range = device.status_range.get(code, None)
                    if status_range and status_range.type == "Enum":
                        try:
                            range_values = json.loads(status_range.values)
                            if value not in range_values.get("range", []):
                                LOGGER.debug(f"mq _on_device_report value not in range value={value}")
                                continue
                        except (json.JSONDecodeError, TypeError) as err:
                            LOGGER.warning(f"mq _on_device_report failed to parse status_range values for {code}: {err}")
                    
                    #LOGGER.debug(f"mq _on_device_report after strategy convert code={code},value={value}")
                    device.status[code] = value
                    updated_status_properties.append(code)
                    if t := item.get("t"):
                        dp_timestamps[code] = t
        else:
            for item in status:
                if "code" in item and "value" in item:
                    code = item["code"]
                    value = item["value"]
                    device.status[code] = value
                    updated_status_properties.append(code)

        self.__update_device(device, updated_status_properties, dp_timestamps)

    def __update_device(
        self,
        device: XTDevice,
        updated_status_properties: list[str] | None = None,
        dp_timestamps: dict | None = None,
    ):
        for listener in self.device_listeners:
            listener.update_device(device, updated_status_properties, dp_timestamps)

    def send_commands(self, device_id: str, commands: list[dict[str, Any]]):
        self.multi_manager.device_watcher.report_message(
            device_id,
            f"Sending Tuya commands: {commands}",
            XTDeviceWatcherCategory.SHARING_API,
        )
        if other_manager := self.get_overriden_device_manager():
            other_manager.send_commands(device_id, commands)
            return
        super().send_commands(device_id, commands)

    def send_lock_unlock_command(
        self,
        device: XTDevice,
        lock: bool,
        force_unlock_mechanism: XTLockingMechanism = XTLockingMechanism.AUTO,
    ) -> bool:
        # I didn't find a way to implement this using the Sharing SDK...
        return False
