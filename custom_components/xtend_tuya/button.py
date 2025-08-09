"""Support for XT buttons."""

from __future__ import annotations
from typing import cast
from dataclasses import dataclass, field
from homeassistant.const import EntityCategory, Platform
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
    XTDPCode,
    VirtualFunctions,
    CROSS_CATEGORY_DEVICE_DESCRIPTOR,  # noqa: F401
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaButtonEntity,
    TuyaButtonEntityDescription,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)


@dataclass(frozen=True)
class XTButtonEntityDescription(TuyaButtonEntityDescription):
    virtual_function: VirtualFunctions | None = None
    vf_reset_state: list[XTDPCode] | None = field(default_factory=list)

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTButtonEntityDescription,
    ) -> XTButtonEntity:
        return XTButtonEntity(
            device=device, device_manager=device_manager, description=description
        )


CONSUMPTION_BUTTONS: tuple[XTButtonEntityDescription, ...] = (
    XTButtonEntityDescription(
        key=XTDPCode.RESET_ADD_ELE,
        virtual_function=VirtualFunctions.FUNCTION_RESET_STATE,
        vf_reset_state=[XTDPCode.ADD_ELE],
        translation_key="reset_add_ele",
        entity_category=EntityCategory.CONFIG,
    ),
)

# All descriptions can be found here.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
BUTTONS: dict[str, tuple[XTButtonEntityDescription, ...]] = {
    "jtmspro": (
        XTButtonEntityDescription(
            key=XTDPCode.MANUAL_LOCK,
            translation_key="manual_lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "kg": (*CONSUMPTION_BUTTONS,),
    "qccdz": (
        XTButtonEntityDescription(
            key=XTDPCode.CLEAR_ENERGY,
            translation_key="clear_energy",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "xfj": (
        XTButtonEntityDescription(
            key=XTDPCode.FILTER_RESET,
            translation_key="filter_reset",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
}

BUTTONS["cz"] = BUTTONS["kg"]
BUTTONS["wkcz"] = BUTTONS["kg"]
BUTTONS["dlq"] = BUTTONS["kg"]
BUTTONS["tdq"] = BUTTONS["kg"]
BUTTONS["pc"] = BUTTONS["kg"]
BUTTONS["aqcz"] = BUTTONS["kg"]

# Lock duplicates
BUTTONS["videolock"] = BUTTONS["jtmspro"]
BUTTONS["jtmsbh"] = BUTTONS["jtmspro"]


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya buttons dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, tuple[XTButtonEntityDescription, ...]],
            dict[str, tuple[XTButtonEntityDescription, ...]],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            BUTTONS, entry.runtime_data.multi_manager, Platform.BUTTON
        ),
    )

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered Tuya buttons."""
        if hass_data.manager is None:
            return
        entities: list[XTButtonEntity] = []
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
                            tuple[XTButtonEntityDescription, ...],
                            restrict_descriptor_category(
                                category_descriptions, [restrict_dpcode]
                            ),
                        )
                    entities.extend(
                        XTButtonEntity.get_entity_instance(
                            description, device, hass_data.manager
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device, description, True, externally_managed_dpcodes
                        )
                    )
                    entities.extend(
                        XTButtonEntity.get_entity_instance(
                            description, device, hass_data.manager
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device, description, False, externally_managed_dpcodes
                        )
                    )
                    for description in category_descriptions:
                        if description.vf_reset_state:
                            for reset_state in description.vf_reset_state:
                                if reset_state in device.status:
                                    entities.append(
                                        XTButtonEntity.get_entity_instance(
                                            description, device, hass_data.manager
                                        )
                                    )
                                break

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors(
        Platform.BUTTON, supported_descriptors
    )
    async_discover_device([*hass_data.manager.device_map])
    # async_discover_device(hass_data.manager, hass_data.manager.open_api_device_map)

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTButtonEntity(XTEntity, TuyaButtonEntity):
    """XT Button Device."""

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTButtonEntityDescription,
    ) -> None:
        """Init XT button."""
        super(XTButtonEntity, self).__init__(device, device_manager, description)
        super(XTEntity, self).__init__(device, device_manager, description)  # type: ignore
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description

    @staticmethod
    def get_entity_instance(
        description: XTButtonEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
    ) -> XTButtonEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(device, device_manager, description)
        return XTButtonEntity(
            device, device_manager, XTButtonEntityDescription(**description.__dict__)
        )
