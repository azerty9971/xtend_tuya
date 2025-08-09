"""Support for Tuya number."""

from __future__ import annotations
from typing import cast
from homeassistant.components.number import (
    NumberDeviceClass,
)
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.number.const import (
    NumberMode,
)
from .util import (
    restrict_descriptor_category,
)
from .const import (
    TUYA_DISCOVERY_NEW,
    XTDPCode,
    CROSS_CATEGORY_DEVICE_DESCRIPTOR,  # noqa: F401
)
from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaNumberEntity,
    TuyaNumberEntityDescription,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)


class XTNumberEntityDescription(TuyaNumberEntityDescription):
    """Describe an Tuya number entity."""

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTNumberEntityDescription,
    ) -> XTNumberEntity:
        return XTNumberEntity(
            device=device, device_manager=device_manager, description=description
        )


TEMPERATURE_SENSORS: tuple[XTNumberEntityDescription, ...] = (
    XTNumberEntityDescription(
        key=XTDPCode.TEMPSET,
        translation_key="temp_set",
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=XTDPCode.TEMP_SET_1,
        translation_key="temp_set",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=XTDPCode.TEMPSC,
        translation_key="tempsc",
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=XTDPCode.TEMP_CALIBRATION,
        translation_key="temp_calibration",
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=XTDPCode.MAXTEMP_SET,
        translation_key="maxtemp_set",
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=XTDPCode.MINITEMP_SET,
        translation_key="minitemp_set",
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=XTDPCode.TEMP_SENSITIVITY,
        translation_key="temp_sensitivity",
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
)

HUMIDITY_SENSORS: tuple[XTNumberEntityDescription, ...] = (
    XTNumberEntityDescription(
        key=XTDPCode.MAXHUM_SET,
        translation_key="maxhum_set",
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=XTDPCode.MINIHUM_SET,
        translation_key="minihum_set",
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=XTDPCode.HUM_SENSITIVITY,
        translation_key="hum_sensitivity",
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=XTDPCode.HUMIDITY_CALIBRATION,
        translation_key="humidity_calibration",
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
    ),
)

TIMER_SENSORS: tuple[XTNumberEntityDescription, ...] = (
    XTNumberEntityDescription(
        key=XTDPCode.COUNTDOWN_1,
        translation_key="countdown_1",
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=XTDPCode.COUNTDOWN_2,
        translation_key="countdown_2",
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=XTDPCode.COUNTDOWN_3,
        translation_key="countdown_3",
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=XTDPCode.COUNTDOWN_4,
        translation_key="countdown_4",
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=XTDPCode.COUNTDOWN_5,
        translation_key="countdown_5",
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=XTDPCode.COUNTDOWN_6,
        translation_key="countdown_6",
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=XTDPCode.COUNTDOWN_7,
        translation_key="countdown_7",
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=XTDPCode.COUNTDOWN_8,
        translation_key="countdown_8",
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=XTDPCode.SETDELAYTIME,
        translation_key="set_delay_time",
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=XTDPCode.SETDEFINETIME,
        translation_key="set_define_time",
        entity_category=EntityCategory.CONFIG,
    ),
)

# All descriptions can be found here. Mostly the Integer data types in the
# default instructions set of each category end up being a number.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
NUMBERS: dict[str, tuple[XTNumberEntityDescription, ...]] = {
    "bh": (
        XTNumberEntityDescription(
            key=XTDPCode.TEMP_SET_1,
            translation_key="warm_temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "dbl": (
        XTNumberEntityDescription(
            key=XTDPCode.VOLUME_SET,
            translation_key="volume",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "ggq": (
        XTNumberEntityDescription(
            key=XTDPCode.COUNTDOWN_1,
            translation_key="countdown_1",
        ),
        XTNumberEntityDescription(
            key=XTDPCode.COUNTDOWN_2,
            translation_key="countdown_2",
        ),
        XTNumberEntityDescription(
            key=XTDPCode.COUNTDOWN_3,
            translation_key="countdown_3",
        ),
        XTNumberEntityDescription(
            key=XTDPCode.COUNTDOWN_4,
            translation_key="countdown_4",
        ),
        XTNumberEntityDescription(
            key=XTDPCode.COUNTDOWN_5,
            translation_key="countdown_5",
        ),
        XTNumberEntityDescription(
            key=XTDPCode.COUNTDOWN_6,
            translation_key="countdown_6",
        ),
        XTNumberEntityDescription(
            key=XTDPCode.COUNTDOWN_7,
            translation_key="countdown_7",
        ),
        XTNumberEntityDescription(
            key=XTDPCode.COUNTDOWN_8,
            translation_key="countdown_8",
        ),
        XTNumberEntityDescription(
            key=XTDPCode.USE_TIME_1,
            translation_key="use_time_1",
        ),
        XTNumberEntityDescription(
            key=XTDPCode.USE_TIME_2,
            translation_key="use_time_2",
        ),
        XTNumberEntityDescription(
            key=XTDPCode.USE_TIME_3,
            translation_key="use_time_3",
        ),
        XTNumberEntityDescription(
            key=XTDPCode.USE_TIME_4,
            translation_key="use_time_4",
        ),
        XTNumberEntityDescription(
            key=XTDPCode.USE_TIME_5,
            translation_key="use_time_5",
        ),
        XTNumberEntityDescription(
            key=XTDPCode.USE_TIME_6,
            translation_key="use_time_6",
        ),
        XTNumberEntityDescription(
            key=XTDPCode.USE_TIME_7,
            translation_key="use_time_7",
        ),
        XTNumberEntityDescription(
            key=XTDPCode.USE_TIME_8,
            translation_key="use_time_8",
        ),
    ),
    "gyd": (
        XTNumberEntityDescription(
            key=XTDPCode.COUNTDOWN,
            translation_key="countdown",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.PIR_DELAY,
            translation_key="pir_delay",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.STANDBY_TIME,
            translation_key="standby_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.STANDBY_BRIGHT,
            translation_key="standby_bright",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "hps": (
        XTNumberEntityDescription(
            key=XTDPCode.NONE_DELAY_TIME,
            translation_key="none_delay_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.NONE_DELAY_TIME_MIN,
            translation_key="none_delay_time_min",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.NONE_DELAY_TIME_SEC,
            translation_key="none_delay_time_sec",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.DETECTION_DISTANCE_MAX,
            translation_key="detection_distance_max",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.DETECTION_DISTANCE_MIN,
            translation_key="detection_distance_min",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.TRIGGER_SENSITIVITY,
            translation_key="trigger_sensitivity",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.HOLD_SENSITIVITY,
            translation_key="hold_sensitivity",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.M_DETECTION_DISTANCE_MAX,
            translation_key="m_detection_distance_max",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.M_DETECTION_DISTANCE_MIN,
            translation_key="m_detection_distance_min",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.M_SENSITIVITY,
            translation_key="m_sensitivity",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.B_DETECTION_DISTANCE_MAX,
            translation_key="b_detection_distance_max",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.B_DETECTION_DISTANCE_MIN,
            translation_key="b_detection_distance_min",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.B_SENSITIVITY,
            translation_key="b_sensitivity",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.SM_DETECTION_DISTANCE_MAX,
            translation_key="b_detection_distance_max",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.SM_DETECTION_DISTANCE_MIN,
            translation_key="b_detection_distance_min",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.SM_SENSITIVITY,
            translation_key="sm_sensitivity",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "jtmspro": (
        XTNumberEntityDescription(
            key=XTDPCode.AUTO_LOCK_TIME,
            translation_key="auto_lock_time",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "kg": (
        XTNumberEntityDescription(
            key=XTDPCode.PRESENCE_DELAY,
            translation_key="presence_delay",
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.MOVESENSITIVITY,
            translation_key="movesensitivity",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.MOVEDISTANCE_MAX,
            translation_key="movedistance_max",
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.MOVEDISTANCE_MIN,
            translation_key="movedistance_min",
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.BREATHSENSITIVITY,
            translation_key="breathsensitivity",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.BREATHDISTANCE_MAX,
            translation_key="breathdistance_max",
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.BREATHDISTANCE_MIN,
            translation_key="breathdistance_min",
            mode=NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
        ),
        *TIMER_SENSORS,
    ),
    "mk": (
        XTNumberEntityDescription(
            key=XTDPCode.AUTO_LOCK_TIME,
            translation_key="auto_lock_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.ALARM_TIME,
            translation_key="alarm_time",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "msp": (
        XTNumberEntityDescription(
            key=XTDPCode.DELAY_CLEAN_TIME,
            translation_key="delay_clean_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.QUIET_TIME_END,
            translation_key="quiet_time_end",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.QUIET_TIME_START,
            translation_key="quiet_time_start",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.SLEEP_START_TIME,
            translation_key="sleep_start_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.SLEEP_END_TIME,
            translation_key="sleep_end_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.UV_START_TIME,
            translation_key="uv_start_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.UV_END_TIME,
            translation_key="uv_end_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.DEO_START_TIME,
            translation_key="deo_start_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.DEO_END_TIME,
            translation_key="deo_end_time",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "mzj": (
        XTNumberEntityDescription(
            key=XTDPCode.RECIPE,
            translation_key="recipe",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.SETTIME,
            translation_key="set_time",
            entity_category=EntityCategory.CONFIG,
        ),
        *TEMPERATURE_SENSORS,
        *HUMIDITY_SENSORS,
    ),
    "qccdz": (
        XTNumberEntityDescription(
            key=XTDPCode.CHARGE_CUR_SET,
            translation_key="charge_cur_set",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.TIMER_ON,
            translation_key="timer_on",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.SET16A,
            translation_key="set_16a",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=True,
            entity_registry_visible_default=False,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.SET32A,
            translation_key="set_32a",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=True,
            entity_registry_visible_default=False,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.SET40A,
            translation_key="set_40a",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=True,
            entity_registry_visible_default=False,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.SET50A,
            translation_key="set_50a",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=True,
            entity_registry_visible_default=False,
        ),
        *TIMER_SENSORS,
    ),
    "wk": (
        *TEMPERATURE_SENSORS,
        *HUMIDITY_SENSORS,
    ),
    "wnykq": (
        XTNumberEntityDescription(
            key=XTDPCode.BRIGHT_VALUE,
            translation_key="bright_value",
            entity_category=EntityCategory.CONFIG,
        ),
        *TEMPERATURE_SENSORS,
        *HUMIDITY_SENSORS,
    ),
    "ywcgq": (
        XTNumberEntityDescription(
            key=XTDPCode.MAX_SET,
            translation_key="max_set",
            mode=NumberMode.SLIDER,
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.MINI_SET,
            translation_key="mini_set",
            mode=NumberMode.SLIDER,
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.INSTALLATION_HEIGHT,
            translation_key="installation_height",
            mode=NumberMode.SLIDER,
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.LIQUID_DEPTH_MAX,
            translation_key="liquid_depth_max",
            mode=NumberMode.SLIDER,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "zwjcy": (
        XTNumberEntityDescription(
            key=XTDPCode.REPORT_SENSITIVITY,
            translation_key="report_sensitivity",
            mode=NumberMode.SLIDER,
            entity_category=EntityCategory.CONFIG,
        ),
        *TEMPERATURE_SENSORS,
        *HUMIDITY_SENSORS,
    ),
}

# Lock duplicates
NUMBERS["videolock"] = NUMBERS["jtmspro"]
NUMBERS["jtmsbh"] = NUMBERS["jtmspro"]


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya number dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, tuple[XTNumberEntityDescription, ...]],
            dict[str, tuple[XTNumberEntityDescription, ...]],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            NUMBERS, entry.runtime_data.multi_manager, Platform.NUMBER
        ),
    )

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered Tuya number."""
        if hass_data.manager is None:
            return
        entities: list[XTNumberEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if category_descriptions := XTEntityDescriptorManager.get_category_descriptors(supported_descriptors, device.category):
                    externally_managed_dpcodes = (
                        XTEntityDescriptorManager.get_category_keys(
                            externally_managed_descriptors.get(device.category)
                        )
                    )
                    if restrict_dpcode is not None:
                        category_descriptions = cast(
                            tuple[XTNumberEntityDescription, ...],
                            restrict_descriptor_category(
                                category_descriptions, [restrict_dpcode]
                            ),
                        )
                    entities.extend(
                        XTNumberEntity.get_entity_instance(
                            description, device, hass_data.manager
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device, description, True, externally_managed_dpcodes
                        )
                    )
                    entities.extend(
                        XTNumberEntity.get_entity_instance(
                            description, device, hass_data.manager
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device, description, False, externally_managed_dpcodes
                        )
                    )

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors(
        Platform.NUMBER, supported_descriptors
    )
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTNumberEntity(XTEntity, TuyaNumberEntity):
    """XT Number Entity."""

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTNumberEntityDescription,
    ) -> None:
        """Init XT number."""
        super(XTNumberEntity, self).__init__(device, device_manager, description)
        super(XTEntity, self).__init__(device, device_manager, description)  # type: ignore
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description

    @staticmethod
    def get_entity_instance(
        description: XTNumberEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
    ) -> XTNumberEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(device, device_manager, description)
        return XTNumberEntity(
            device, device_manager, XTNumberEntityDescription(**description.__dict__)
        )
