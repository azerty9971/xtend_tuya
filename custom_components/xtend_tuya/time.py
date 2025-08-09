from __future__ import annotations
from typing import cast
from dataclasses import dataclass
from datetime import time, datetime
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.time import (
    TimeEntity,
    TimeEntityDescription,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import Platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .const import (
    TUYA_DISCOVERY_NEW,
    CROSS_CATEGORY_DEVICE_DESCRIPTOR,  # noqa: F401
)
from .util import (
    restrict_descriptor_category,
)
from .multi_manager.multi_manager import (
    MultiManager,
    XTConfigEntry,
    XTDevice,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)


@dataclass(frozen=True)
class XTTimeEntityDescription(TimeEntityDescription):
    """Describes a Tuya time."""

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTTimeEntityDescription,
    ) -> XTTimeEntity:
        return XTTimeEntity(
            device=device, device_manager=device_manager, description=description
        )


TIMES: dict[str, tuple[XTTimeEntityDescription, ...]] = {}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya binary sensor dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, tuple[XTTimeEntityDescription, ...]],
            dict[str, tuple[XTTimeEntityDescription, ...]],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            TIMES, entry.runtime_data.multi_manager, Platform.TIME
        ),
    )

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered Tuya binary sensor."""
        if hass_data.manager is None:
            return
        entities: list[XTTimeEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if category_descriptions := XTEntityDescriptorManager.get_category_descriptors(supported_descriptors, device.category):
                    externally_managed_dpcodes = (
                        XTEntityDescriptorManager.get_category_keys(
                            externally_managed_descriptors.get(device.category)
                        )
                    )
                    if restrict_dpcode is not None:
                        category_descriptions = cast(
                            tuple[XTTimeEntityDescription, ...],
                            restrict_descriptor_category(
                                category_descriptions, [restrict_dpcode]
                            ),
                        )
                    entities.extend(
                        XTTimeEntity.get_entity_instance(
                            description, device, hass_data.manager
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device, description, True, externally_managed_dpcodes
                        )
                    )
                    entities.extend(
                        XTTimeEntity.get_entity_instance(
                            description, device, hass_data.manager
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device, description, False, externally_managed_dpcodes
                        )
                    )

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors(Platform.TIME, supported_descriptors)
    async_discover_device([*hass_data.manager.device_map])
    # async_discover_device(hass_data.manager, hass_data.manager.open_api_device_map)

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTTimeEntity(XTEntity, TimeEntity):  # type: ignore
    """XT Time entity."""

    entity_description: XTTimeEntityDescription

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTTimeEntityDescription,
    ) -> None:
        """Init XT time."""
        super().__init__(device, device_manager)
        self.entity_description = description  # type: ignore
        self.device = device
        self.device_manager = device_manager

    @property
    def native_value(self) -> time | None:  # type: ignore
        """Return the latest value."""
        return datetime.now().time()

    def set_value(self, value: time) -> None:
        """Change the time."""
        raise NotImplementedError

    @staticmethod
    def get_entity_instance(
        description: XTTimeEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
    ) -> XTTimeEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(device, device_manager, description)
        return XTTimeEntity(
            device, device_manager, XTTimeEntityDescription(**description.__dict__)
        )
