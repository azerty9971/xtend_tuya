from homeassistant.config_entries import ConfigEntry
from typing import NamedTuple

class MultiManager:
    pass

class XTDeviceStatusRange:
    pass

class XTDeviceFunction:
    pass

class XTDeviceProperties:
    pass

class HomeAssistantXTData:
    pass

class TuyaIntegrationRuntimeData(NamedTuple):
    pass

type XTConfigEntry = ConfigEntry[HomeAssistantXTData]