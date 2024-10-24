from __future__ import annotations

from typing import (
    NamedTuple,
)

from .ha_tuya_integration.config_entry_handler import (
    XTHATuyaIntegrationConfigEntryManager,
)

from .xt_tuya_sharing_manager import (
    XTSharingDeviceManager,
)

class TuyaSharingData(NamedTuple):
    device_manager: XTSharingDeviceManager
    device_ids: list[str] #List of device IDs that are managed by the manager before the managers device merging process
    ha_tuya_integration_config_manager: XTHATuyaIntegrationConfigEntryManager