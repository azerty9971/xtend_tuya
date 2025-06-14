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
from .const import TUYA_DISCOVERY_NEW, XTDPCode, CROSS_CATEGORY_DEVICE_DESCRIPTOR
from .entity import (
    XTEntity,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaSelectEntity,
    TuyaSelectEntityDescription,
)

class XTSelectEntityDescription(TuyaSelectEntityDescription):
    """Describe an Tuya select entity."""

    def get_entity_instance(self, 
                            device: XTDevice, 
                            device_manager: MultiManager, 
                            description: XTSelectEntityDescription
                            ) -> XTSelectEntity:
        return XTSelectEntity(device=device, 
                              device_manager=device_manager, 
                              description=description)

TEMPERATURE_SELECTS: tuple[XTSelectEntityDescription, ...] = (
    XTSelectEntityDescription(
        key=XTDPCode.TEMP_UNIT_CONVERT,
        translation_key="change_temp_unit",
        entity_category=EntityCategory.CONFIG,
    ),
    XTSelectEntityDescription(
        key=XTDPCode.TEMPCHANGER,
        translation_key="change_temp_unit",
        entity_category=EntityCategory.CONFIG,
    ),
)

# All descriptions can be found here. Mostly the Enum data types in the
# default instructions set of each category end up being a select.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
SELECTS: dict[str, tuple[XTSelectEntityDescription, ...]] = {
    "cz": (
        XTSelectEntityDescription(
            key=XTDPCode.SOLAR_EN_TOTAL,
            translation_key="solar_en_total",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "dbl": (
        XTSelectEntityDescription(
            key=XTDPCode.COUNTDOWN_SET,
            translation_key="countdown",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=XTDPCode.POWER_SET,
            translation_key="dbl_power_set",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=XTDPCode.SOUND_MODE,
            translation_key="sound_mode",
            entity_category=EntityCategory.CONFIG,
        ),
        *TEMPERATURE_SELECTS,
    ),
    "dj": (
        XTSelectEntityDescription(
            key=XTDPCode.COLOR,
            translation_key="dj_color",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=XTDPCode.MODE2,
            translation_key="dj_mode",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "ggq": (
        XTSelectEntityDescription(
            key=XTDPCode.WEATHER_DELAY,
            translation_key="weather_delay",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=XTDPCode.WATER_CONTROL,
            translation_key="water_control",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=XTDPCode.TEMP_UNIT_CONVERT,
            translation_key="temp_unit_convert",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "gyd": (
        XTSelectEntityDescription(
            key=XTDPCode.DEVICE_MODE,
            translation_key="device_mode",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=XTDPCode.CDS,
            translation_key="cds",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=XTDPCode.PIR_SENSITIVITY,
            translation_key="pir_sensitivity",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "jtmspro": (
        XTSelectEntityDescription(
            key=XTDPCode.BEEP_VOLUME,
            translation_key="beep_volume",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=XTDPCode.ALARM_VOLUME,
            translation_key="alarm_volume",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False
        ),
        XTSelectEntityDescription(
            key=XTDPCode.SOUND_MODE,
            translation_key="sound_mode",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False
        ),
    ),
    "mk": (
        XTSelectEntityDescription(
            key=XTDPCode.DOORBELL_VOLUME,
            translation_key="doorbell_volume",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "MPPT": (
        XTSelectEntityDescription(
            key=XTDPCode.TEMPUNIT,
            translation_key="tempunit",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=XTDPCode.UNIT2,
            translation_key="currency",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "msp": (
        XTSelectEntityDescription(
            key=XTDPCode.CLEAN,
            translation_key="cat_litter_box_clean",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=XTDPCode.EMPTY,
            translation_key="cat_litter_box_empty",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=XTDPCode.STATUS,
            translation_key="cat_litter_box_status",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        XTSelectEntityDescription(
            key=XTDPCode.WORK_MODE,
            translation_key="cat_litter_box_work_mode",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "ms_category": (
        XTSelectEntityDescription(
            key=XTDPCode.KEY_TONE,
            translation_key="key_tone",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "mzj": (
        *TEMPERATURE_SELECTS,
    ),
    "qccdz": (
        XTSelectEntityDescription(
            key=XTDPCode.WORK_MODE,
            translation_key="qccdz_work_mode",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=XTDPCode.CHARGINGOPERATION,
            translation_key="qccdz_chargingoperation",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "sfkzq": (
        XTSelectEntityDescription(
            key=XTDPCode.WORK_STATE,
            translation_key="sfkzq_work_state",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "wk": (
        *TEMPERATURE_SELECTS,
    ),
    "xfj": (
        XTSelectEntityDescription(
            key=XTDPCode.MODE,
            translation_key="xfj_mode",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "zwjcy": (
        *TEMPERATURE_SELECTS,
    ),
}

#Lock duplicates
SELECTS["videolock"] = SELECTS["jtmspro"]
SELECTS["jtmsbh"] = SELECTS["jtmspro"]

async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya select dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    merged_descriptors = SELECTS
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.SELECT):
        merged_descriptors = merge_device_descriptors(merged_descriptors, new_descriptor)

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered Tuya select."""
        if hass_data.manager is None:
            return
        entities: list[XTSelectEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if descriptions := merged_descriptors.get(device.category):
                    entities.extend(
                        XTSelectEntity.get_entity_instance(description, device, hass_data.manager)
                        for description in descriptions
                        if description.key in device.status and (restrict_dpcode is None or restrict_dpcode == description.key)
                    )
                if descriptions := merged_descriptors.get(CROSS_CATEGORY_DEVICE_DESCRIPTOR):
                    entities.extend(
                        XTSelectEntity.get_entity_instance(description, device, hass_data.manager)
                        for description in descriptions
                        if description.key in device.status and (restrict_dpcode is None or restrict_dpcode == description.key)
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
        super(XTEntity, self).__init__(device, device_manager, description) # type: ignore
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description
    
    @staticmethod
    def get_entity_instance(description: XTSelectEntityDescription, device: XTDevice, device_manager: MultiManager) -> XTSelectEntity:
        if hasattr(description, "get_entity_instance") and callable(getattr(description, "get_entity_instance")):
            return description.get_entity_instance(device, device_manager, description)
        return XTSelectEntity(device, device_manager, XTSelectEntityDescription(**description.__dict__))