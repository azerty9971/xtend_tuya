"""Support for XT switches."""

from __future__ import annotations

from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .util import (
    merge_device_descriptors
)

from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .const import TUYA_DISCOVERY_NEW, DPCode
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaSwitchEntity,
    TuyaSwitchEntityDescription,
)
from .entity import (
    XTEntity,
)

class XTSwitchEntityDescription(TuyaSwitchEntityDescription, frozen_or_thawed=True):
    override_tuya: bool = False

# All descriptions can be found here. Mostly the Boolean data types in the
# default instruction set of each category end up being a Switch.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
SWITCHES: dict[str, tuple[XTSwitchEntityDescription, ...]] = {
    "dbl": (
        XTSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:human-child"
        ),
        XTSwitchEntityDescription(
            key=DPCode.SOUND,
            translation_key="sound",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "ggq": (
        XTSwitchEntityDescription(
            key=DPCode.SWITCH_1,
            translation_key="switch_1",
        ),
        XTSwitchEntityDescription(
            key=DPCode.SWITCH_2,
            translation_key="switch_2",
        ),
        XTSwitchEntityDescription(
            key=DPCode.SWITCH_3,
            translation_key="switch_3",
        ),
        XTSwitchEntityDescription(
            key=DPCode.SWITCH_4,
            translation_key="switch_4",
        ),
        XTSwitchEntityDescription(
            key=DPCode.SWITCH_5,
            translation_key="switch_5",
        ),
        XTSwitchEntityDescription(
            key=DPCode.SWITCH_6,
            translation_key="switch_6",
        ),
        XTSwitchEntityDescription(
            key=DPCode.SWITCH_7,
            translation_key="switch_7",
        ),
        XTSwitchEntityDescription(
            key=DPCode.SWITCH_8,
            translation_key="switch_8",
        ),
        XTSwitchEntityDescription(
            key=DPCode.WEATHER_SWITCH,
            translation_key="weather_switch",
        ),
        XTSwitchEntityDescription(
            key=DPCode.CONTROL_SKIP,
            translation_key="control_skip",
        ),
        XTSwitchEntityDescription(
            key=DPCode.SWITCH_ENABLED,
            translation_key="switch_enabled",
        ),
    ),
    "gyd": (
        XTSwitchEntityDescription(
            key=DPCode.SWITCH_PIR,
            translation_key="switch_pir",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "hps": (
        XTSwitchEntityDescription(
            key=DPCode.INDICATOR_LED,
            translation_key="indicator_light",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "jtmspro": (
        XTSwitchEntityDescription(
            key=DPCode.AUTOMATIC_LOCK,
            translation_key="automatic_lock",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.ALARM_SWITCH,
            translation_key="alarm_switch",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False
        ),
    ),
    "mk": (
        XTSwitchEntityDescription(
            key=DPCode.AUTOMATIC_LOCK,
            translation_key="automatic_lock",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False
        ),
        XTSwitchEntityDescription(
            key=DPCode.PHOTO_AGAIN,
            translation_key="photo_again",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False
        ),
    ),
    # Automatic cat litter box
    # Note: Undocumented
    "msp": (
        XTSwitchEntityDescription(
            key=DPCode.AUTO_CLEAN,
            translation_key="auto_clean",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:bacteria",
        ),
        XTSwitchEntityDescription(
            key=DPCode.AUTO_DEORDRIZER,
            translation_key="auto_deordrizer",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.BEEP,
            translation_key="beep",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.CALIBRATION,
            translation_key="calibration",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:human-child"
        ),
        XTSwitchEntityDescription(
            key=DPCode.CLEAN_NOTICE,
            translation_key="clean_notice",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.CLEAN_TASTE_SWITCH,
            translation_key="clean_tasteswitch",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.CLEAN_TIME_SWITCH,
            translation_key="clean_time_switch",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.DEODORIZATION,
            translation_key="deodorization",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:bacteria",
        ),
        XTSwitchEntityDescription(
            key=DPCode.FACTORY_RESET,
            translation_key="factory_reset",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
        ),
        XTSwitchEntityDescription(
            key=DPCode.INDICATOR_LIGHT,
            translation_key="indicator_light",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.INDUCTION_CLEAN,
            translation_key="induction_clean",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.LIGHT,
            translation_key="light",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.MANUAL_CLEAN,
            translation_key="manual_clean",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.NET_NOTICE,
            translation_key="net_notice",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
        ),
        XTSwitchEntityDescription(
            key=DPCode.NOT_DISTURB_SWITCH,
            translation_key="not_disturb_switch",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.ODOURLESS,
            translation_key="odourless",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.CLEANING,
            translation_key="one_click_cleanup",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.QUIET_TIMING_ON,
            translation_key="quiet_timing_on",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.REBOOT,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
        ),
        XTSwitchEntityDescription(
            key=DPCode.SLEEP,
            translation_key="sleep",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.SLEEPING,
            translation_key="sleeping",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.SMART_CLEAN,
            translation_key="smart_clean",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.START,
            translation_key="start",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:bacteria",
        ),
        XTSwitchEntityDescription(
            key=DPCode.STORE_FULL_NOTIFY,
            translation_key="store_full_notify",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
        ),
        XTSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.TOILET_NOTICE,
            translation_key="toilet_notice",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:toilet"
        ),
        XTSwitchEntityDescription(
            key=DPCode.UNIT,
            translation_key="unit",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
        ),
        XTSwitchEntityDescription(
            key=DPCode.UV,
            translation_key="uv",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "mzj": (
        XTSwitchEntityDescription(
            key=DPCode.POWERONOFF,
            translation_key="power",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "qccdz": (
        XTSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.RFID,
            translation_key="rfid",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.IDVERIFICATIONSET,
            translation_key="id_verification_set",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "wnykq": (
        XTSwitchEntityDescription(
            key=DPCode.POWERON,
            translation_key="power",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "xfj": (
        XTSwitchEntityDescription(
            key=DPCode.SWITCH,
            translation_key="switch",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.UV_LIGHT,
            translation_key="uv_light",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=DPCode.ANION,
            translation_key="anion",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
}

#Lock duplicates
SWITCHES["videolock"] = SWITCHES["jtmspro"]

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
        entities: list[XTSwitchEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if descriptions := merged_descriptors.get(device.category):
                    entities.extend(
                        XTSwitchEntity(device, hass_data.manager, XTSwitchEntityDescription(**description.__dict__))
                        for description in descriptions
                        if description.key in device.status
                    )

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors("switches", merged_descriptors)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTSwitchEntity(XTEntity, TuyaSwitchEntity):
    """XT Switch Device."""

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSwitchEntityDescription,
    ) -> None:
        """Init TuyaHaSwitch."""
        super(XTSwitchEntity, self).__init__(device, device_manager, description)
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description

