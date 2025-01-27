"""Support for XT scenes."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaSceneEntity,
    TuyaScene,
)

class XTScene(TuyaScene):
    pass

async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya scenes."""
    hass_data = entry.runtime_data
    scenes = await hass.async_add_executor_job(hass_data.manager.query_scenes)
    async_add_entities(XTSceneEntity(hass_data.manager, XTScene(**scene.__dict__)) for scene in scenes)


class XTSceneEntity(TuyaSceneEntity):
    """XT Scene Entity."""

    def __init__(self, multi_manager: MultiManager, scene: XTScene) -> None:
        """Init Tuya Scene."""
        super(XTSceneEntity, self).__init__(multi_manager, scene)
        self.home_manager = multi_manager
        self.scene = scene
        if self._attr_unique_id not in multi_manager.scene_id:
            multi_manager.scene_id.append(self._attr_unique_id)
