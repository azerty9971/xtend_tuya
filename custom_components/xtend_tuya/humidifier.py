"""Support for XT (de)humidifiers."""

from __future__ import annotations
from dataclasses import dataclass
from typing import cast
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
    TuyaHumidifierRoundedIntegerWrapper,
    TuyaDPCodeEnumWrapper,
    TuyaDPCodeBooleanWrapper,
    TuyaDPCode,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)


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
        *,
        current_humidity_wrapper: TuyaHumidifierRoundedIntegerWrapper | None = None,
        mode_wrapper: TuyaDPCodeEnumWrapper | None = None,
        switch_wrapper: TuyaDPCodeBooleanWrapper | None = None,
        target_humidity_wrapper: TuyaHumidifierRoundedIntegerWrapper | None = None,
    ) -> XTHumidifierEntity:
        return XTHumidifierEntity(
            device=device,
            device_manager=device_manager,
            description=XTHumidifierEntityDescription(**description.__dict__),
            current_humidity_wrapper=current_humidity_wrapper,
            mode_wrapper=mode_wrapper,
            switch_wrapper=switch_wrapper,
            target_humidity_wrapper=target_humidity_wrapper,
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
                if description := cast(XTHumidifierEntityDescription, XTEntityDescriptorManager.get_category_descriptors(
                    supported_descriptors, device.category
                )):
                    entities.append(
                        XTHumidifierEntity.get_entity_instance(
                            description,
                            device,
                            hass_data.manager,
                            current_humidity_wrapper=TuyaHumidifierRoundedIntegerWrapper.find_dpcode(
                                device, description.current_humidity
                            ),
                            mode_wrapper=TuyaDPCodeEnumWrapper.find_dpcode(
                                device, TuyaDPCode.MODE, prefer_function=True
                            ),
                            switch_wrapper=TuyaDPCodeBooleanWrapper.find_dpcode(
                                device,
                                description.dpcode or description.key,
                                prefer_function=True,
                            ),
                            target_humidity_wrapper=TuyaHumidifierRoundedIntegerWrapper.find_dpcode(
                                device, description.humidity, prefer_function=True
                            ),
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
        *,
        current_humidity_wrapper: TuyaHumidifierRoundedIntegerWrapper | None = None,
        mode_wrapper: TuyaDPCodeEnumWrapper | None = None,
        switch_wrapper: TuyaDPCodeBooleanWrapper | None = None,
        target_humidity_wrapper: TuyaHumidifierRoundedIntegerWrapper | None = None,
    ) -> None:
        super(XTHumidifierEntity, self).__init__(device, device_manager, description)
        super(XTEntity, self).__init__(
            device,
            device_manager,  # type: ignore
            description,
            current_humidity_wrapper=current_humidity_wrapper,
            mode_wrapper=mode_wrapper,
            switch_wrapper=switch_wrapper,
            target_humidity_wrapper=target_humidity_wrapper,
        )
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description

    @staticmethod
    def get_entity_instance(
        description: XTHumidifierEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
        *,
        current_humidity_wrapper: TuyaHumidifierRoundedIntegerWrapper | None = None,
        mode_wrapper: TuyaDPCodeEnumWrapper | None = None,
        switch_wrapper: TuyaDPCodeBooleanWrapper | None = None,
        target_humidity_wrapper: TuyaHumidifierRoundedIntegerWrapper | None = None,
    ) -> XTHumidifierEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(
                device,
                device_manager,
                description,
                current_humidity_wrapper=current_humidity_wrapper,
                mode_wrapper=mode_wrapper,
                switch_wrapper=switch_wrapper,
                target_humidity_wrapper=target_humidity_wrapper,
            )
        return XTHumidifierEntity(
            device,
            device_manager,
            XTHumidifierEntityDescription(**description.__dict__),
            current_humidity_wrapper=current_humidity_wrapper,
            mode_wrapper=mode_wrapper,
            switch_wrapper=switch_wrapper,
            target_humidity_wrapper=target_humidity_wrapper,
        )
