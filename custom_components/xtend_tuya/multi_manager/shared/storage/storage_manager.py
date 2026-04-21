from __future__ import annotations
from typing import TYPE_CHECKING, Any
import json
from dataclasses import dataclass, field
from homeassistant.helpers.storage import Store
from ....const import (
    LOGGER,
    XTAcceptableStoragePropertyValue,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from ..shared_classes import (
        XTConfigEntry,
    )
    from ...multi_manager import (
        MultiManager,
    )


@dataclass
class XTStorageStructure:
    type DeviceId = str
    type DPCode = str
    type PropertyName = str

    device_configurable_properties: dict[
        XTStorageStructure.DeviceId,
        dict[
            XTStorageStructure.DPCode,
            dict[XTStorageStructure.PropertyName, XTAcceptableStoragePropertyValue],
        ],
    ] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return_dict: dict[str, Any] = {}
        return_dict["device_configurable_properties"] = json.dumps(
            self.device_configurable_properties
        )
        return return_dict

    @staticmethod
    def from_dict(raw_dict: dict[str, Any]) -> XTStorageStructure:
        new_dict: dict[str, Any] = {}
        if (
            device_configurable_properties := raw_dict.get(
                "device_configurable_properties"
            )
        ) is not None:
            new_dict["device_configurable_properties"] = json.loads(
                device_configurable_properties
            )
        return XTStorageStructure(**new_dict)


class XTStorageManager:
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: XTConfigEntry,
        multi_manager: MultiManager,
    ) -> None:
        self._store = Store(
            hass=hass, version=1, key=f"xtend_tuya_{config_entry.entry_id}"
        )
        self._store_data: XTStorageStructure = XTStorageStructure()
        self._multi_manager: MultiManager = multi_manager

    def get_device_configurable_property(
        self,
        device_id: XTStorageStructure.DeviceId,
        dpcode: XTStorageStructure.DPCode,
        prop_name: XTStorageStructure.PropertyName,
    ) -> XTAcceptableStoragePropertyValue | None:
        if (
            device_id in self._store_data.device_configurable_properties
            and dpcode in self._store_data.device_configurable_properties[device_id]
            and prop_name
            in self._store_data.device_configurable_properties[device_id][dpcode]
        ):
            return self._store_data.device_configurable_properties[device_id][dpcode][
                prop_name
            ]
        return None

    def set_device_configurable_property(
        self,
        device_id: XTStorageStructure.DeviceId,
        dpcode: XTStorageStructure.DPCode,
        prop_name: XTStorageStructure.PropertyName,
        prop_value: XTAcceptableStoragePropertyValue,
    ):
        if device_id not in self._store_data.device_configurable_properties:
            self._store_data.device_configurable_properties[device_id] = {}
        if dpcode not in self._store_data.device_configurable_properties[device_id]:
            self._store_data.device_configurable_properties[device_id][dpcode] = {}
        self._store_data.device_configurable_properties[device_id][dpcode][
            prop_name
        ] = prop_value

    async def load_store(self) -> bool:
        try:
            stored_data = await self._store.async_load()
            if stored_data is not None:
                self._store_data = XTStorageStructure.from_dict(stored_data)
        except Exception as e:
            LOGGER.exception(e)
            return False
        return True

    async def save_store(self) -> bool:
        try:
            await self._store.async_save(self._store_data.as_dict())
        except Exception as e:
            LOGGER.exception(e)
            return False
        return True
