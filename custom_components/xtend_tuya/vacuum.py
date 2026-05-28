"""Support for Tuya Vacuums."""

from __future__ import annotations
from typing import cast
from tuya_device_handlers.definition.vacuum import (
    VacuumDefinition,
    get_default_definition,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.components.vacuum import (
    StateVacuumEntityDescription,
)

from .multi_manager.multi_manager import (
    MultiManager,
    XTConfigEntry,
    XTDevice,
)
from .const import TUYA_DISCOVERY_NEW, XTDPCode
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaVacuumEntity,
)

CHARGE_DPCODE = (XTDPCode.SWITCH_CHARGE,)
FAN_SPEED_DPCODE = (XTDPCode.SUCTION,)
LOCATE_DPCODE = (XTDPCode.SEEK,)
MODE_DPCODE = (XTDPCode.MODE,)
PAUSE_DPCODE = (XTDPCode.PAUSE,)
STATUS_DPCODE = (XTDPCode.STATUS,)
SWITCH_DPCODE = (XTDPCode.POWER_GO,)


class XTVacuumEntityDescription(StateVacuumEntityDescription, frozen_or_thawed=True):
    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTVacuumEntityDescription,
        definition: VacuumDefinition,
    ) -> XTVacuumEntity:
        return XTVacuumEntity(
            device=device,
            device_manager=device_manager,
            description=XTVacuumEntityDescription(**description.__dict__),
            definition=definition,
        )


VACUUMS: dict[str, XTVacuumEntityDescription] = {}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya vacuum dynamically through Tuya discovery."""
    hass_data = entry.runtime_data
    this_platform = Platform.VACUUM

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, XTVacuumEntityDescription],
            dict[str, XTVacuumEntityDescription],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            VACUUMS,
            entry.runtime_data.multi_manager,
            XTVacuumEntityDescription,
            this_platform,
        ),
    )

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered Tuya vacuum."""
        if hass_data.manager is None:
            return
        if restrict_dpcode is not None:
            return None
        entities: list[XTVacuumEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if device.category in supported_descriptors:
                    entities.append(
                        XTVacuumEntity.get_entity_instance(
                            device=device,
                            device_manager=hass_data.manager,
                            description=supported_descriptors[device.category],
                            definition=get_default_definition(device),
                        )
                    )
        async_add_entities(entities)

    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTVacuumEntity(XTEntity, TuyaVacuumEntity):
    """XT Vacuum Device."""

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTVacuumEntityDescription,
        definition: VacuumDefinition,
    ) -> None:
        """Init Tuya vacuum."""
        super(XTVacuumEntity, self).__init__(
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

    @staticmethod
    def get_entity_instance(
        device: XTDevice,
        device_manager: MultiManager,
        description: XTVacuumEntityDescription,
        definition: VacuumDefinition,
    ) -> XTVacuumEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(
                device=device,
                device_manager=device_manager,
                description=description,
                definition=definition,
            )
        return XTVacuumEntity(
            device=device,
            device_manager=device_manager,
            description=XTVacuumEntityDescription(**description.__dict__),
            definition=definition,
        )
