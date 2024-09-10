from __future__ import annotations

from dataclasses import dataclass, field

from .ha_tuya_integration.config_entry_handler import (
    XTHATuyaIntegrationConfigEntryManager,
)

from .xt_tuya_sharing_manager import (
    XTSharingDeviceManager,
)

@dataclass
class TuyaSharingData:
    device_manager: XTSharingDeviceManager = None
    device_ids: list[str] = field(default_factory=list) #List of device IDs that are managed by the manager before the managers device merging process
    ha_tuya_integration_config_manager: XTHATuyaIntegrationConfigEntryManager = None