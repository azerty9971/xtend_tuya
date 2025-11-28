"""Support for Tuya event entities."""

from __future__ import annotations
from typing import Any, cast
from dataclasses import dataclass
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
    LOGGER,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaEventEntity,
    TuyaEventEntityDescription,
    TuyaEventDPCodeEventWrapper,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)


@dataclass(frozen=True)
class XTEventEntityDescription(TuyaEventEntityDescription):
    override_tuya: bool = False
    dont_send_to_cloud: bool = False
    on_value: Any = None
    off_value: Any = None

    # duplicate the entity if handled by another integration
    ignore_other_dp_code_handler: bool = False

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTEventEntityDescription,
        dpcode_wrapper: TuyaEventDPCodeEventWrapper,
    ) -> XTEventEntity:
        return XTEventEntity(
            device=device,
            device_manager=device_manager,
            description=XTEventEntityDescription(**description.__dict__),
            dpcode_wrapper=dpcode_wrapper,
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
    this_platform = Platform.EVENT

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, tuple[XTEventEntityDescription, ...]],
            dict[str, tuple[XTEventEntityDescription, ...]],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            EVENTS,
            entry.runtime_data.multi_manager,
            XTEventEntityDescription,
            this_platform,
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
                if category_descriptions := XTEntityDescriptorManager.get_category_descriptors(
                    supported_descriptors, device.category
                ):
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
                            description,
                            device,
                            hass_data.manager,
                            dpcode_wrapper,
                        )
                        for description in category_descriptions
                        if (
                            XTEntity.supports_description(
                                device,
                                this_platform,
                                description,
                                True,
                                externally_managed_dpcodes,
                            )
                            and (
                                dpcode_wrapper := description.wrapper_class.find_dpcode(
                                    device, description.key
                                )
                            )
                        )
                    )
                    entities.extend(
                        XTEventEntity.get_entity_instance(
                            description,
                            device,
                            hass_data.manager,
                            dpcode_wrapper,
                        )
                        for description in category_descriptions
                        if (
                            XTEntity.supports_description(
                                device,
                                this_platform,
                                description,
                                False,
                                externally_managed_dpcodes,
                            )
                            and (
                                dpcode_wrapper := description.wrapper_class.find_dpcode(
                                    device, description.key
                                )
                            )
                        )
                    )

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors(this_platform, supported_descriptors)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTEventEntity(XTEntity, TuyaEventEntity):
    """Tuya Event Entity."""

    entity_description: XTEventEntityDescription

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTEventEntityDescription,
        dpcode_wrapper: TuyaEventDPCodeEventWrapper,
    ) -> None:
        """Init Tuya event entity."""
        try:
            super(XTEventEntity, self).__init__(device, device_manager, description)
            super(XTEntity, self).__init__(
                device,
                device_manager,  # type: ignore
                description,
                dpcode_wrapper=dpcode_wrapper,
            )
        except Exception as e:
            LOGGER.warning(f"Events failed to initialize, is your HA up to date? ({e})")
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description  # type: ignore

    @staticmethod
    def get_entity_instance(
        description: XTEventEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
        dpcode_wrapper: TuyaEventDPCodeEventWrapper,
    ) -> XTEventEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(
                device,
                device_manager,
                description,
                dpcode_wrapper,
            )
        return XTEventEntity(
            device,
            device_manager,
            XTEventEntityDescription(**description.__dict__),
            dpcode_wrapper,
        )
