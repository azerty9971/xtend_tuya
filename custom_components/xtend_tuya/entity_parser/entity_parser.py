from __future__ import annotations
import os
from functools import partial
import importlib
from typing import Any
from abc import abstractmethod
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from ..const import LOGGER
import custom_components.xtend_tuya.multi_manager.multi_manager as mm


class XTCustomEntityParser:
    def __init__(self) -> None:
        pass

    @abstractmethod
    def get_descriptors_to_merge(self, platform: Platform) -> Any:
        pass

    @staticmethod
    async def setup_entity_parsers(
        hass: HomeAssistant, multi_manager: mm.MultiManager
    ) -> None:
        # Load all the plugins
        # subdirs = await self.hass.async_add_executor_job(os.listdir, os.path.dirname(__file__))
        subdirs = await hass.async_add_executor_job(
            partial(os.listdir, path=os.path.dirname(__file__))
        )
        for directory in subdirs:
            if directory.startswith("__"):
                continue
            if os.path.isdir(os.path.dirname(__file__) + os.sep + directory):
                load_path = f".{directory}.init"
                try:
                    plugin = await hass.async_add_executor_job(
                        partial(
                            importlib.import_module, name=load_path, package=__package__
                        )
                    )
                    instance: XTCustomEntityParser | None = plugin.get_plugin_instance()
                    if instance is not None:
                        multi_manager.entity_parsers[directory] = instance
                except ModuleNotFoundError as e:
                    LOGGER.error(f"Loading entity parser {directory} failed: {e}")
