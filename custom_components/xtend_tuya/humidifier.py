"""Support for XT (de)humidifiers."""

from __future__ import annotations
from dataclasses import dataclass
from typing import cast
from tuya_device_handlers.definition.humidifier import (
    HumidifierDefinition,
    get_default_definition,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .const import TUYA_DISCOVERY_NEW
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaHumidifierEntity,
    TuyaHumidifierEntityDescription,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)

COMPOUND_KEY: list[str | tuple[str, ...]] = ["key", "dpcode"]


@dataclass(frozen=True)
class XTHumidifierEntityDescription(TuyaHumidifierEntityDescription):
    """Describe an XT (de)humidifier entity."""

    # duplicate the entity if handled by another integration
    ignore_other_dp_code_handler: bool = False

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTHumidifierEntityDescription,
        definition: HumidifierDefinition,
    ) -> XTHumidifierEntity:
        return XTHumidifierEntity(
            device=device,
            device_manager=device_manager,
            description=XTHumidifierEntityDescription(**description.__dict__),
            definition=definition,
        )


HUMIDIFIERS: dict[str, XTHumidifierEntityDescription] = {}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya (de)humidifier dynamically through Tuya discovery."""
    hass_data = entry.runtime_data
    this_platform = Platform.HUMIDIFIER

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, XTHumidifierEntityDescription],
            dict[str, XTHumidifierEntityDescription],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            HUMIDIFIERS,
            entry.runtime_data.multi_manager,
            XTHumidifierEntityDescription,
            this_platform,
            COMPOUND_KEY,
        ),
    )

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered Tuya (de)humidifier."""
        if hass_data.manager is None:
            return
        if restrict_dpcode is not None:
            return None
        entities: list[XTHumidifierEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if description := cast(
                    XTHumidifierEntityDescription,
                    XTEntityDescriptorManager.get_category_descriptors(
                        supported_descriptors, device.category
                    ),
                ):
                    if definition := get_default_definition(
                        device,
                        switch_dpcode=description.dpcode or description.key,
                        current_humidity_dpcode=description.current_humidity,
                        humidity_dpcode=description.humidity,
                    ):
                        entities.append(
                            XTHumidifierEntity.get_entity_instance(
                                device=device,
                                device_manager=hass_data.manager,
                                description=description,
                                definition=definition,
                            )
                        )
        async_add_entities(entities)

    hass_data.manager.register_device_descriptors(this_platform, supported_descriptors)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTHumidifierEntity(XTEntity, TuyaHumidifierEntity):
    """XT (de)humidifier Device."""

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTHumidifierEntityDescription,
        definition: HumidifierDefinition,
    ) -> None:
        super(XTHumidifierEntity, self).__init__(
            device=device,
            device_manager=device_manager,  # type: ignore
            description=description,
            definition=definition,
        )
        super(XTEntity, self).__init__(
            device=device,
            device_manager=device_manager,  # type: ignore
            description=description,
            definition=definition,
        )
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description

    @staticmethod
    def get_entity_instance(
        device: XTDevice,
        device_manager: MultiManager,
        description: XTHumidifierEntityDescription,
        definition: HumidifierDefinition,
    ) -> XTHumidifierEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(
                device=device,
                device_manager=device_manager,
                description=description,
                definition=definition,
            )
        return XTHumidifierEntity(
            device=device,
            device_manager=device_manager,
            description=XTHumidifierEntityDescription(**description.__dict__),
            definition=definition,
        )
