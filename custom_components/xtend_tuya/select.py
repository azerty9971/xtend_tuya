"""Support for Tuya select."""

from __future__ import annotations
from typing import cast
from dataclasses import dataclass
from tuya_device_handlers.definition.select import (
    SelectDefinition,
    get_default_definition,
)
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
    CROSS_CATEGORY_DEVICE_DESCRIPTOR,
    TUYA_DISCOVERY_NEW,
    XTDPCode,
    XTMultiManagerPostSetupCallbackPriority,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaSelectEntity,
    TuyaSelectEntityDescription,
)


@dataclass(frozen=True)
class XTSelectEntityDescription(TuyaSelectEntityDescription):
    """Describe an Tuya select entity."""

    # Custom options
    options: list[str] | None = None

    # duplicate the entity if handled by another integration
    ignore_other_dp_code_handler: bool = False

    dont_send_to_cloud: bool = False

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSelectEntityDescription,
        definition: SelectDefinition,
    ) -> XTSelectEntity:
        return XTSelectEntity(
            device=device,
            device_manager=device_manager,
            description=XTSelectEntityDescription(**description.__dict__),
            definition=definition,
        )


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
    CROSS_CATEGORY_DEVICE_DESCRIPTOR: (
    ),
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
            key=XTDPCode.MODE_CAP,
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
            entity_registry_enabled_default=False,
        ),
        XTSelectEntityDescription(
            key=XTDPCode.SOUND_MODE,
            translation_key="sound_mode",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
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
    "ms_category": (
        XTSelectEntityDescription(
            key=XTDPCode.KEY_TONE,
            translation_key="key_tone",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "msp": (
        XTSelectEntityDescription(
            key=XTDPCode.CHOOSE_CAT_LITTER,
            translation_key="cat_litter_type",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=XTDPCode.WORK_MODE,
            translation_key="cat_litter_box_work_mode",
            entity_category=EntityCategory.CONFIG,
        ),
        # Ti+ / DOEL ti+TpCTbt-01: weight unit selector
        XTSelectEntityDescription(
            key=XTDPCode.UNIT_SWITCH,
            translation_key="unit_switch",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "mzj": (*TEMPERATURE_SELECTS,),
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
    # QT-08W Solar Intelligent Water Valve
    "sfkzq": (
        XTSelectEntityDescription(
            key=XTDPCode.WORK_STATE,
            translation_key="sfkzq_work_state",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSelectEntityDescription(
            key=XTDPCode.TEMP_UNIT,
            translation_key="temperature_unit",
            entity_category=EntityCategory.CONFIG,
            options=["1", "2"],
        ),
        XTSelectEntityDescription(
            key=XTDPCode.CAPACITY_UNIT,
            translation_key="volume_unit",
            entity_category=EntityCategory.CONFIG,
            options=["L", "Gal"],
        ),
    ),
    "wk": (*TEMPERATURE_SELECTS,),
    "xfj": (
        XTSelectEntityDescription(
            key=XTDPCode.MODE,
            translation_key="xfj_mode",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "zwjcy": (*TEMPERATURE_SELECTS,),
}

# Lock duplicates
SELECTS["videolock"] = SELECTS["jtmspro"]
SELECTS["jtmsbh"] = SELECTS["jtmspro"]


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya select dynamically through Tuya discovery."""
    hass_data = entry.runtime_data
    this_platform = Platform.SELECT

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, tuple[XTSelectEntityDescription, ...]],
            dict[str, tuple[XTSelectEntityDescription, ...]],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            SELECTS,
            entry.runtime_data.multi_manager,
            XTSelectEntityDescription,
            this_platform,
        ),
    )

    @callback
    def async_add_generic_entities(device_map) -> None:
        if hass_data.manager is None:
            return
        entities: list[XTSelectEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                generic_dpcodes = XTEntity.get_generic_dpcodes_for_this_platform(
                    device, this_platform
                )
                for dpcode in generic_dpcodes:
                    description = XTSelectEntityDescription(
                        key=dpcode,
                        translation_key="xt_generic_select",
                        translation_placeholders={
                            "name": XTEntity.get_human_name(dpcode)
                        },
                        entity_registry_enabled_default=False,
                        entity_registry_visible_default=False,
                    )
                    if definition := get_default_definition(device, description.key):
                        entities.append(
                            XTSelectEntity.get_entity_instance(
                                description=description,
                                device=device,
                                device_manager=hass_data.manager,
                                definition=definition,
                            )
                        )
        async_add_entities(entities)

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered Tuya select."""
        if hass_data.manager is None:
            return
        entities: list[XTSelectEntity] = []
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
                            tuple[XTSelectEntityDescription, ...],
                            restrict_descriptor_category(
                                category_descriptions, [restrict_dpcode]
                            ),
                        )
                    entities.extend(
                        XTSelectEntity.get_entity_instance(
                            description=description,
                            device=device,
                            device_manager=hass_data.manager,
                            definition=definition,
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
                                definition := get_default_definition(device, description.key)
                            )
                        )
                    )
                    entities.extend(
                        XTSelectEntity.get_entity_instance(
                            description=description,
                            device=device,
                            device_manager=hass_data.manager,
                            definition=definition,
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
                                definition := get_default_definition(
                                    device, description.key
                                )
                            )
                        )
                    )

        async_add_entities(entities)
        if restrict_dpcode is None:
            hass_data.manager.add_post_setup_callback(
                XTMultiManagerPostSetupCallbackPriority.PRIORITY_LAST,
                async_add_generic_entities,
                device_map,
            )

    hass_data.manager.register_device_descriptors(this_platform, supported_descriptors)
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
        definition: SelectDefinition,
    ) -> None:
        """Init XT select."""
        super(XTSelectEntity, self).__init__(
            device=device,
            device_manager=device_manager,
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
        self.entity_description = description

        # Use custom options
        if description.options is not None:
            for option in description.options:
                if option not in self._attr_options:
                    self._attr_options.append(option)

    @staticmethod
    def get_entity_instance(
        description: XTSelectEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
        definition: SelectDefinition,
    ) -> XTSelectEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(
                device=device,
                device_manager=device_manager,
                description=description,
                definition=definition,
            )
        return XTSelectEntity(
            device=device,
            device_manager=device_manager,
            description=XTSelectEntityDescription(**description.__dict__),
            definition=definition,
        )

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if hasattr(self.entity_description, "dont_send_to_cloud") and self.entity_description.dont_send_to_cloud:  # type: ignore
            self.device.status[self.entity_description.key] = option
            self.device_manager.multi_device_listener.update_device(
                self.device, [self.entity_description.key]
            )
        else:
            await super().async_select_option(option)
