from __future__ import annotations
from ....lib.tuya_iot import (
    TuyaHomeManager,
    TuyaOpenAPI,
    TuyaOpenMQ,
)
from ....lib.tuya_iot.asset import TuyaAssetManager
from ....lib.tuya_iot.tuya_enums import AuthType
from ...multi_manager import (
    MultiManager,
)
from ...shared.threading import (
    XTConcurrencyManager,
    XTEventLoopProtector,
)
from .xt_tuya_iot_manager import (
    XTIOTDeviceManager,
)


class XTIOTHomeManager(TuyaHomeManager):
    def __init__(
        self,
        api: TuyaOpenAPI,
        mq: TuyaOpenMQ,
        device_manager: XTIOTDeviceManager,
        multi_manager: MultiManager,
    ):
        super().__init__(api, mq, device_manager)
        self.multi_manager = multi_manager
        self.device_manager = device_manager

    async def async_query_device_ids(
        self, asset_manager: TuyaAssetManager, asset_id: str, device_ids: list
    ) -> list:
        if asset_id != "-1":
            device_ids += await XTEventLoopProtector.execute_out_of_event_loop_and_return(asset_manager.get_device_list, asset_id)
        assets = await XTEventLoopProtector.execute_out_of_event_loop_and_return(asset_manager.get_asset_list, asset_id)
        concurrency_manager = XTConcurrencyManager(max_concurrency=9)
        for asset in assets:
            concurrency_manager.add_coroutine(self.async_query_device_ids(asset_manager, asset["asset_id"], device_ids))
        await concurrency_manager.gather()
        return device_ids

    async def async_update_device_cache(self):
        """Update home's devices cache."""
        self.device_manager.device_map.clear()
        if self.api.auth_type == AuthType.CUSTOM:
            device_ids = []
            asset_manager = TuyaAssetManager(self.api)

            await self.async_query_device_ids(asset_manager, "-1", device_ids)

            # assets = asset_manager.get_asset_list()
            # for asset in assets:
            #     asset_id = asset["asset_id"]
            #     device_ids += asset_manager.get_device_list(asset_id)
            if device_ids:
                await self.device_manager.async_update_device_caches(device_ids)
        elif self.api.auth_type == AuthType.SMART_HOME:
            await self.device_manager.async_update_device_list_in_smart_home()

    def update_device_cache(self):
        super().update_device_cache()
        # self.multi_manager.convert_tuya_devices_to_xt(self.device_manager)
