"""Support for Tuya switches."""

from __future__ import annotations

from typing import Any

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.switch import (
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .util import (
    merge_device_descriptors
)

from .multi_manager.multi_manager import XTConfigEntry
from .base import TuyaEntity
from .const import TUYA_DISCOVERY_NEW, DPCode

# All descriptions can be found here. Mostly the Boolean data types in the
# default instruction set of each category end up being a Switch.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
SWITCHES: dict[str, tuple[SwitchEntityDescription, ...]] = {
    "jtmspro": (
        SwitchEntityDescription(
            key=DPCode.AUTOMATIC_LOCK,
            translation_key="automatic_lock",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.ALARM_SWITCH,
            translation_key="alarm_switch",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # Automatic cat litter box
    # Note: Undocumented
    "msp": (
        SwitchEntityDescription(
            key=DPCode.AUTO_CLEAN,
            translation_key="auto_clean",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:bacteria",
        ),
        SwitchEntityDescription(
            key=DPCode.AUTO_DEORDRIZER,
            translation_key="auto_deordrizer",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.BEEP,
            translation_key="beep",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.CALIBRATION,
            translation_key="calibration",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:human-child"
        ),
        SwitchEntityDescription(
            key=DPCode.CLEAN_NOTICE,
            translation_key="clean_notice",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.CLEAN_TASTE_SWITCH,
            translation_key="clean_tasteswitch",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.CLEAN_TIME_SWITCH,
            translation_key="clean_time_switch",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.DEODORIZATION,
            translation_key="deodorization",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:bacteria",
        ),
        SwitchEntityDescription(
            key=DPCode.FACTORY_RESET,
            translation_key="factory_reset",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
        ),
        SwitchEntityDescription(
            key=DPCode.INDICATOR_LIGHT,
            translation_key="indicator_light",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.INDUCTION_CLEAN,
            translation_key="induction_clean",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.LIGHT,
            translation_key="light",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.MANUAL_CLEAN,
            translation_key="manual_clean",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.NET_NOTICE,
            translation_key="net_notice",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
        ),
        SwitchEntityDescription(
            key=DPCode.NOT_DISTURB_SWITCH,
            translation_key="not_disturb_switch",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.ODOURLESS,
            translation_key="odourless",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.CLEANING,
            translation_key="one_click_cleanup",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.QUIET_TIMING_ON,
            translation_key="quiet_timing_on",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.REBOOT,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
        ),
        SwitchEntityDescription(
            key=DPCode.SLEEP,
            translation_key="sleep",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SLEEPING,
            translation_key="sleeping",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.SMART_CLEAN,
            translation_key="smart_clean",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.START,
            translation_key="start",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:bacteria",
        ),
        SwitchEntityDescription(
            key=DPCode.STORE_FULL_NOTIFY,
            translation_key="store_full_notify",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
        ),
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
            entity_category=EntityCategory.CONFIG,
        ),
        SwitchEntityDescription(
            key=DPCode.TOILET_NOTICE,
            translation_key="toilet_notice",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:toilet"
        ),
        SwitchEntityDescription(
            key=DPCode.UNIT,
            translation_key="unit",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
        ),
        SwitchEntityDescription(
            key=DPCode.UV,
            translation_key="uv",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "mzj": (
        SwitchEntityDescription(
            key=DPCode.POWERONOFF,
            translation_key="power",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "wnykq": (
        SwitchEntityDescription(
            key=DPCode.POWERON,
            translation_key="power",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up tuya sensors dynamically through tuya discovery."""
    hass_data = entry.runtime_data

    merged_descriptors = SWITCHES
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.SWITCH):
        merged_descriptors = merge_device_descriptors(merged_descriptors, new_descriptor)

    @callback
    def async_discover_device(device_map) -> None:
        """Discover and add a discovered tuya sensor."""
        entities: list[TuyaSwitchEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if descriptions := merged_descriptors.get(device.category):
                    entities.extend(
                        TuyaSwitchEntity(device, hass_data.manager, description)
                        for description in descriptions
                        if description.key in device.status
                    )

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors("switches", merged_descriptors)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaSwitchEntity(TuyaEntity, SwitchEntity):
    """Tuya Switch Device."""

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: SwitchEntityDescription,
    ) -> None:
        """Init TuyaHaSwitch."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.device.status.get(self.entity_description.key, False)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._send_command([{"code": self.entity_description.key, "value": True}])

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._send_command([{"code": self.entity_description.key, "value": False}])
