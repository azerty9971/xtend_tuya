"""Support for Tuya select."""

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
from .entity import (
    XTEntity,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaSelectEntity,
    TuyaSelectEntityDescription,
)

class XTSelectEntityDescription(TuyaSelectEntityDescription):
    """Describe an Tuya select entity."""
    pass

# All descriptions can be found here. Mostly the Enum data types in the
# default instructions set of each category end up being a select.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
SELECTS: dict[str, tuple[XTSelectEntityDescription, ...]] = {
    "dbl": (
        XTSelectEntityDescription(
            key=DPCode.TEMP_UNIT_CONVERT,
            translation_key="change_temp_unit",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=DPCode.COUNTDOWN_SET,
            translation_key="countdown",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=DPCode.POWER_SET,
            translation_key="dbl_power_set",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=DPCode.SOUND_MODE,
            translation_key="sound_mode",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "dj": (
        XTSelectEntityDescription(
            key=DPCode.COLOR,
            translation_key="dj_color",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=DPCode.MODE2,
            translation_key="dj_mode",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "ggq": (
        XTSelectEntityDescription(
            key=DPCode.WEATHER_DELAY,
            translation_key="weather_delay",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=DPCode.WATER_CONTROL,
            translation_key="water_control",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=DPCode.TEMP_UNIT_CONVERT,
            translation_key="temp_unit_convert",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "gyd": (
        XTSelectEntityDescription(
            key=DPCode.DEVICE_MODE,
            translation_key="device_mode",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=DPCode.CDS,
            translation_key="cds",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=DPCode.PIR_SENSITIVITY,
            translation_key="pir_sensitivity",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "jtmspro": (
        XTSelectEntityDescription(
            key=DPCode.BEEP_VOLUME,
            translation_key="beep_volume",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=DPCode.ALARM_VOLUME,
            translation_key="alarm_volume",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False
        ),
        XTSelectEntityDescription(
            key=DPCode.SOUND_MODE,
            translation_key="sound_mode",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False
        ),
    ),
    "mk": (
        XTSelectEntityDescription(
            key=DPCode.DOORBELL_VOLUME,
            translation_key="doorbell_volume",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "msp": (
        XTSelectEntityDescription(
            key=DPCode.CLEAN,
            translation_key="cat_litter_box_clean",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=DPCode.EMPTY,
            translation_key="cat_litter_box_empty",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=DPCode.STATUS,
            translation_key="cat_litter_box_status",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        XTSelectEntityDescription(
            key=DPCode.WORK_MODE,
            translation_key="cat_litter_box_work_mode",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "ms_category": (
        XTSelectEntityDescription(
            key=DPCode.KEY_TONE,
            translation_key="key_tone",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "mzj": (
        XTSelectEntityDescription(
            key=DPCode.TEMPCHANGER,
            translation_key="change_temp_unit",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "qccdz": (
        XTSelectEntityDescription(
            key=DPCode.WORK_MODE,
            translation_key="qccdz_work_mode",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=DPCode.CHARGINGOPERATION,
            translation_key="qccdz_chargingoperation",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "sfkzq": (
        XTSelectEntityDescription(
            key=DPCode.WORK_STATE,
            translation_key="sfkzq_work_state",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "xfj": (
        XTSelectEntityDescription(
            key=DPCode.MODE,
            translation_key="xfj_mode",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya select dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    merged_descriptors = SELECTS
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.SELECT):
        merged_descriptors = merge_device_descriptors(merged_descriptors, new_descriptor)

    @callback
    def async_discover_device(device_map) -> None:
        """Discover and add a discovered Tuya select."""
        entities: list[XTSelectEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if descriptions := merged_descriptors.get(device.category):
                    entities.extend(
                        XTSelectEntity(device, hass_data.manager, XTSelectEntityDescription(**description.__dict__))
                        for description in descriptions
                        if description.key in device.status
                    )

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors("selects", merged_descriptors)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTSelectEntity(XTEntity, TuyaSelectEntity):
    """XT Select Entity."""

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSelectEntityDescription,
    ) -> None:
        """Init XT select."""
        super(XTSelectEntity, self).__init__(device, device_manager, description)
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description