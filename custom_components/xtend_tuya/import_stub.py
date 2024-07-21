from types import SimpleNamespace
from homeassistant.config_entries import ConfigEntry

class MultiManager:
    pass

class XTDeviceStatusRange:
    pass

class XTDeviceFunction:
    pass

class XTDeviceProperties(SimpleNamespace):
    pass

class HomeAssistantXTData:
    pass

type XTConfigEntry = ConfigEntry[HomeAssistantXTData]