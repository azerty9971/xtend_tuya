"""Support for Tuya event entities."""

from __future__ import annotations
from typing import Any, cast
from homeassistant.components.event import (
    EventEntityDescription,
    EventDeviceClass,  # noqa: F401
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .util import (
    restrict_descriptor_category,
)
from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .const import (
    TUYA_DISCOVERY_NEW,
    XTDPCode,  # noqa: F401
    CROSS_CATEGORY_DEVICE_DESCRIPTOR,  # noqa: F401
    LOGGER,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaEventEntity,
    TuyaDPType,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)


class XTEventEntityDescription(EventEntityDescription, frozen_or_thawed=True):
    override_tuya: bool = False
    dont_send_to_cloud: bool = False
    on_value: Any = None
    off_value: Any = None

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTEventEntityDescription,
    ) -> XTEventEntity:
        return XTEventEntity(
            device=device, device_manager=device_manager, description=description
        )


# All descriptions can be found here. Mostly the Enum data types in the
# default status set of each category (that don't have a set instruction)
# end up being events.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
EVENTS: dict[str, tuple[XTEventEntityDescription, ...]] = {}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up tuya sensors dynamically through tuya discovery."""
    hass_data = entry.runtime_data

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, tuple[XTEventEntityDescription, ...]],
            dict[str, tuple[XTEventEntityDescription, ...]],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            EVENTS, entry.runtime_data.multi_manager, Platform.EVENT
        ),
    )

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered tuya sensor."""
        if hass_data.manager is None:
            return
        entities: list[XTEventEntity] = []
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
                            tuple[XTEventEntityDescription, ...],
                            restrict_descriptor_category(
                                category_descriptions, [restrict_dpcode]
                            ),
                        )
                    entities.extend(
                        XTEventEntity.get_entity_instance(
                            description, device, hass_data.manager
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device, description, True, externally_managed_dpcodes
                        )
                    )
                    entities.extend(
                        XTEventEntity.get_entity_instance(
                            description, device, hass_data.manager
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device, description, False, externally_managed_dpcodes
                        )
                    )

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors(Platform.EVENT, supported_descriptors)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTEventEntity(XTEntity, TuyaEventEntity):
    """Tuya Event Entity."""

    entity_description: EventEntityDescription

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: EventEntityDescription,
    ) -> None:
        """Init Tuya event entity."""
        try:
            super(XTEventEntity, self).__init__(device, device_manager, description)
            super(XTEntity, self).__init__(device, device_manager, description)  # type: ignore
        except Exception as e:
            LOGGER.warning(f"Events failed to initialize, is your HA up to date? ({e})")
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description  # type: ignore

        if dpcode := self.find_dpcode(description.key, dptype=TuyaDPType.ENUM):
            self._attr_event_types: list[str] = dpcode.range

    async def _handle_state_update(
        self, updated_status_properties: list[str] | None
    ) -> None:
        if (
            updated_status_properties is None
            or self.entity_description.key not in updated_status_properties
        ):
            return

        value = self.device.status.get(self.entity_description.key)
        if value is not None and isinstance(value, str):
            self._trigger_event(value)
        self.async_write_ha_state()

    @staticmethod
    def get_entity_instance(
        description: XTEventEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
    ) -> XTEventEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(device, device_manager, description)
        return XTEventEntity(
            device, device_manager, XTEventEntityDescription(**description.__dict__)
        )
