"""Support for XT Alarm."""

from __future__ import annotations
from typing import cast
from homeassistant.const import (
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .util import (
    restrict_descriptor_category,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaAlarmEntity,
    TuyaAlarmControlPanelEntityDescription,
)
from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .const import TUYA_DISCOVERY_NEW
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)


class XTAlarmEntityDescription(TuyaAlarmControlPanelEntityDescription):
    def __init__(self, *args, **kwargs):
        super(XTAlarmEntityDescription, self).__init__(*args, **kwargs)

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTAlarmEntityDescription,
    ) -> XTAlarmEntity:
        return XTAlarmEntity(
            device=device, device_manager=device_manager, description=description
        )


# All descriptions can be found here:
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
ALARM: dict[str, tuple[XTAlarmEntityDescription, ...]] = {}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya alarm dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, tuple[XTAlarmEntityDescription, ...]],
            dict[str, tuple[XTAlarmEntityDescription, ...]],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            ALARM, entry.runtime_data.multi_manager, Platform.ALARM_CONTROL_PANEL
        ),
    )

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered Tuya siren."""
        entities: list[XTAlarmEntity] = []
        device_ids = [*device_map]
        if hass_data.manager is None:
            return
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id, None):
                if category_descriptions := XTEntityDescriptorManager.get_category_descriptors(supported_descriptors, device.category):
                    externally_managed_dpcodes = (
                        XTEntityDescriptorManager.get_category_keys(
                            externally_managed_descriptors.get(device.category)
                        )
                    )
                    if restrict_dpcode is not None:
                        category_descriptions = cast(
                            tuple[XTAlarmEntityDescription, ...],
                            restrict_descriptor_category(
                                category_descriptions, [restrict_dpcode]
                            ),
                        )
                    entities.extend(
                        XTAlarmEntity.get_entity_instance(
                            description, device, hass_data.manager
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device, description, True, externally_managed_dpcodes
                        )
                    )
                    entities.extend(
                        XTAlarmEntity.get_entity_instance(
                            description, device, hass_data.manager
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device, description, False, externally_managed_dpcodes
                        )
                    )
        async_add_entities(entities)

    hass_data.manager.register_device_descriptors(
        Platform.ALARM_CONTROL_PANEL, supported_descriptors
    )
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTAlarmEntity(XTEntity, TuyaAlarmEntity):
    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTAlarmEntityDescription,
    ) -> None:
        super(XTAlarmEntity, self).__init__(device, device_manager, description)
        super(XTEntity, self).__init__(device, device_manager, description)  # type: ignore

    @staticmethod
    def get_entity_instance(
        description: XTAlarmEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
    ) -> XTAlarmEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(device, device_manager, description)
        return XTAlarmEntity(
            device, device_manager, XTAlarmEntityDescription(**description.__dict__)
        )
