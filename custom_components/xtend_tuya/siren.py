"""Support for Tuya siren."""

from __future__ import annotations
from typing import cast
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
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaSirenEntity,
    TuyaSirenEntityDescription,
    TuyaDPCodeBooleanWrapper,
)


@dataclass(frozen=True)
class XTSirenEntityDescription(TuyaSirenEntityDescription, frozen_or_thawed=True):

    # duplicate the entity if handled by another integration
    ignore_other_dp_code_handler: bool = False

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSirenEntityDescription,
        dpcode_wrapper: TuyaDPCodeBooleanWrapper,
    ) -> XTSirenEntity:
        return XTSirenEntity(
            device=device,
            device_manager=device_manager,
            description=XTSirenEntityDescription(**description.__dict__),
            dpcode_wrapper=dpcode_wrapper,
        )


# All descriptions can be found here:
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
SIRENS: dict[str, tuple[XTSirenEntityDescription, ...]] = {}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya siren dynamically through Tuya discovery."""
    hass_data = entry.runtime_data
    this_platform = Platform.SIREN

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, tuple[XTSirenEntityDescription, ...]],
            dict[str, tuple[XTSirenEntityDescription, ...]],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            SIRENS,
            entry.runtime_data.multi_manager,
            XTSirenEntityDescription,
            this_platform,
        ),
    )

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered Tuya siren."""
        if hass_data.manager is None:
            return
        entities: list[XTSirenEntity] = []
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
                            tuple[XTSirenEntityDescription, ...],
                            restrict_descriptor_category(
                                category_descriptions, [restrict_dpcode]
                            ),
                        )
                    entities.extend(
                        XTSirenEntity.get_entity_instance(
                            description, device, hass_data.manager, dpcode_wrapper
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
                                dpcode_wrapper := TuyaDPCodeBooleanWrapper.find_dpcode(
                                    device, description.key, prefer_function=True
                                )
                            )
                        )
                    )
                    entities.extend(
                        XTSirenEntity.get_entity_instance(
                            description, device, hass_data.manager, dpcode_wrapper
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
                                dpcode_wrapper := TuyaDPCodeBooleanWrapper.find_dpcode(
                                    device, description.key, prefer_function=True
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


class XTSirenEntity(XTEntity, TuyaSirenEntity):
    """XT Siren Entity."""

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSirenEntityDescription,
        dpcode_wrapper: TuyaDPCodeBooleanWrapper,
    ) -> None:
        """Init XT Siren."""
        super(XTSirenEntity, self).__init__(device, device_manager, description)
        super(XTEntity, self).__init__(
            device,
            device_manager,  # type: ignore
            description,
            dpcode_wrapper,
        )
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description

    @staticmethod
    def get_entity_instance(
        description: XTSirenEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
        dpcode_wrapper: TuyaDPCodeBooleanWrapper,
    ) -> XTSirenEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(
                device,
                device_manager,
                description,
                dpcode_wrapper,
            )
        return XTSirenEntity(
            device,
            device_manager,
            XTSirenEntityDescription(**description.__dict__),
            dpcode_wrapper,
        )
