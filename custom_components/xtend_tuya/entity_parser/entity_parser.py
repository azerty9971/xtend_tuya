from __future__ import annotations

import os
from functools import partial
import importlib
from typing import Any

from homeassistant.const import (
    Platform
)
from homeassistant.core import (
    HomeAssistant
)

from ..const import LOGGER
from ..multi_manager.multi_manager import (
    MultiManager,
)

class XTCustomEntityParser:
    def __init__(self) -> None:
        pass

    def get_descriptors_to_merge(self, platform: Platform) -> Any:
        return None

    @staticmethod
    async def setup_entity_parsers(hass: HomeAssistant, multi_manager: MultiManager) -> None:
        #Load all the plugins
        #subdirs = await self.hass.async_add_executor_job(os.listdir, os.path.dirname(__file__))
        subdirs = os.listdir(os.path.dirname(__file__))
        for directory in subdirs:
            if directory.startswith("__"):
                continue
            if os.path.isdir(os.path.dirname(__file__) + os.sep + directory):
                load_path = f".{directory}.init"
                try:
                    plugin = await hass.async_add_executor_job(partial(importlib.import_module, name=load_path, package=__package__))
                    instance: XTCustomEntityParser | None = plugin.get_plugin_instance()
                    if instance is not None:
                        multi_manager.entity_parsers[directory] = instance
                except ModuleNotFoundError as e:
                    LOGGER.error(f"Loading entity parser {directory} failed: {e}")