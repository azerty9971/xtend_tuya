from homeassistant.config_entries import ConfigEntry

class MultiManager:
    pass

from .shared_classes import (  # noqa: E402
    HomeAssistantXTData
)

#class HomeAssistantXTData:
#    pass

type XTConfigEntry = ConfigEntry[HomeAssistantXTData]