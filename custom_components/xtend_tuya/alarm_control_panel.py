"""Support for XT Alarm."""

from __future__ import annotations
from typing import cast
from dataclasses import dataclass
from tuya_device_handlers.definition.alarm_control_panel import (
    AlarmControlPanelDefinition,
    get_default_definition,
)
from homeassistant.const import (
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
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


@dataclass(frozen=True)
class XTAlarmEntityDescription(TuyaAlarmControlPanelEntityDescription):
    # duplicate the entity if handled by another integration
    ignore_other_dp_code_handler: bool = False

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTAlarmEntityDescription,
        definition: AlarmControlPanelDefinition,
    ) -> XTAlarmEntity:
        return XTAlarmEntity(
            device=device,
            device_manager=device_manager,
            description=XTAlarmEntityDescription(**description.__dict__),
            definition=definition,
        )


# All descriptions can be found here:
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
ALARM: dict[str, XTAlarmEntityDescription] = {}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya alarm dynamically through Tuya discovery."""
    hass_data = entry.runtime_data
    this_platform = Platform.ALARM_CONTROL_PANEL

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, XTAlarmEntityDescription],
            dict[str, XTAlarmEntityDescription],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            ALARM,
            entry.runtime_data.multi_manager,
            XTAlarmEntityDescription,
            this_platform,
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
                if category_descriptions := cast(
                    XTAlarmEntityDescription,
                    XTEntityDescriptorManager.get_category_descriptors(
                        supported_descriptors, device.category
                    ),
                ):
                    externally_managed_dpcodes = (
                        XTEntityDescriptorManager.get_category_keys(
                            externally_managed_descriptors.get(device.category)
                        )
                    )
                    if XTEntity.supports_description(
                        device,
                        this_platform,
                        category_descriptions,
                        True,
                        externally_managed_dpcodes,
                    ) and (definition := get_default_definition(device)):
                        entities.append(
                            XTAlarmEntity.get_entity_instance(
                                device=device,
                                device_manager=hass_data.manager,
                                description=category_descriptions,
                                definition=definition,
                            )
                        )
                    if XTEntity.supports_description(
                        device,
                        this_platform,
                        category_descriptions,
                        False,
                        externally_managed_dpcodes,
                    ) and (definition := get_default_definition(device)):
                        entities.append(
                            XTAlarmEntity.get_entity_instance(
                                device=device,
                                device_manager=hass_data.manager,
                                description=category_descriptions,
                                definition=definition,
                            )
                        )
        async_add_entities(entities)

    hass_data.manager.register_device_descriptors(this_platform, supported_descriptors)
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
        definition: AlarmControlPanelDefinition,
    ) -> None:
        super(XTAlarmEntity, self).__init__(
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

    @staticmethod
    def get_entity_instance(
        device: XTDevice,
        device_manager: MultiManager,
        description: XTAlarmEntityDescription,
        definition: AlarmControlPanelDefinition,
    ) -> XTAlarmEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(
                device=device,
                device_manager=device_manager,
                description=description,
                definition=definition,
            )
        return XTAlarmEntity(
            device=device,
            device_manager=device_manager,
            description=XTAlarmEntityDescription(
                **description.__dict__,
            ),
            definition=definition,
        )
