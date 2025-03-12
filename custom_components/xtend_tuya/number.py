"""Support for Tuya number."""

from __future__ import annotations


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
    merge_device_descriptors
)

from .const import TUYA_DISCOVERY_NEW, DPCode
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
)

class XTNumberEntityDescription(TuyaNumberEntityDescription):
    """Describe an Tuya number entity."""
    pass

TIMER_SENSORS: tuple[XTNumberEntityDescription, ...] = (
    XTNumberEntityDescription(
        key=DPCode.COUNTDOWN_1,
        translation_key="countdown_1",
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=DPCode.COUNTDOWN_2,
        translation_key="countdown_2",
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=DPCode.COUNTDOWN_3,
        translation_key="countdown_3",
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=DPCode.COUNTDOWN_4,
        translation_key="countdown_4",
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=DPCode.COUNTDOWN_5,
        translation_key="countdown_5",
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=DPCode.COUNTDOWN_6,
        translation_key="countdown_6",
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=DPCode.COUNTDOWN_7,
        translation_key="countdown_7",
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=DPCode.COUNTDOWN_8,
        translation_key="countdown_8",
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=DPCode.SETDELAYTIME,
        translation_key="set_delay_time",
        entity_category=EntityCategory.CONFIG,
    ),
    XTNumberEntityDescription(
        key=DPCode.SETDEFINETIME,
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
            key=DPCode.TEMP_SET_1,
            translation_key="warm_temperature",
            device_class=NumberDeviceClass.TEMPERATURE,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "dbl": (
        XTNumberEntityDescription(
            key=DPCode.VOLUME_SET,
            translation_key="volume",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "ggq": (
        XTNumberEntityDescription(
            key=DPCode.COUNTDOWN_1,
            translation_key="countdown_1",
        ),
        XTNumberEntityDescription(
            key=DPCode.COUNTDOWN_2,
            translation_key="countdown_2",
        ),
        XTNumberEntityDescription(
            key=DPCode.COUNTDOWN_3,
            translation_key="countdown_3",
        ),
        XTNumberEntityDescription(
            key=DPCode.COUNTDOWN_4,
            translation_key="countdown_4",
        ),
        XTNumberEntityDescription(
            key=DPCode.COUNTDOWN_5,
            translation_key="countdown_5",
        ),
        XTNumberEntityDescription(
            key=DPCode.COUNTDOWN_6,
            translation_key="countdown_6",
        ),
        XTNumberEntityDescription(
            key=DPCode.COUNTDOWN_7,
            translation_key="countdown_7",
        ),
        XTNumberEntityDescription(
            key=DPCode.COUNTDOWN_8,
            translation_key="countdown_8",
        ),
        XTNumberEntityDescription(
            key=DPCode.USE_TIME_1,
            translation_key="use_time_1",
        ),
        XTNumberEntityDescription(
            key=DPCode.USE_TIME_2,
            translation_key="use_time_2",
        ),
        XTNumberEntityDescription(
            key=DPCode.USE_TIME_3,
            translation_key="use_time_3",
        ),
        XTNumberEntityDescription(
            key=DPCode.USE_TIME_4,
            translation_key="use_time_4",
        ),
        XTNumberEntityDescription(
            key=DPCode.USE_TIME_5,
            translation_key="use_time_5",
        ),
        XTNumberEntityDescription(
            key=DPCode.USE_TIME_6,
            translation_key="use_time_6",
        ),
        XTNumberEntityDescription(
            key=DPCode.USE_TIME_7,
            translation_key="use_time_7",
        ),
        XTNumberEntityDescription(
            key=DPCode.USE_TIME_8,
            translation_key="use_time_8",
        ),
    ),
    "gyd": (
        XTNumberEntityDescription(
            key=DPCode.COUNTDOWN,
            translation_key="countdown",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.PIR_DELAY,
            translation_key="pir_delay",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.STANDBY_TIME,
            translation_key="standby_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.STANDBY_BRIGHT,
            translation_key="standby_bright",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "hps": (
        XTNumberEntityDescription(
            key=DPCode.NONE_DELAY_TIME,
            translation_key="none_delay_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.NONE_DELAY_TIME_MIN,
            translation_key="none_delay_time_min",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.NONE_DELAY_TIME_SEC,
            translation_key="none_delay_time_sec",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.DETECTION_DISTANCE_MAX,
            translation_key="detection_distance_max",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.DETECTION_DISTANCE_MIN,
            translation_key="detection_distance_min",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.TRIGGER_SENSITIVITY,
            translation_key="trigger_sensitivity",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.HOLD_SENSITIVITY,
            translation_key="hold_sensitivity",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "jtmspro": (
        XTNumberEntityDescription(
            key=DPCode.AUTO_LOCK_TIME,
            translation_key="auto_lock_time",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "kg": (
        XTNumberEntityDescription(
            key=DPCode.PRESENCE_DELAY,
            translation_key="presence_delay",
            mode = NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.MOVESENSITIVITY,
            translation_key="movesensitivity",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.MOVEDISTANCE_MAX,
            translation_key="movedistance_max",
            mode = NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.MOVEDISTANCE_MIN,
            translation_key="movedistance_min",
            mode = NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.BREATHSENSITIVITY,
            translation_key="breathsensitivity",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.BREATHDISTANCE_MAX,
            translation_key="breathdistance_max",
            mode = NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.BREATHDISTANCE_MIN,
            translation_key="breathdistance_min",
            mode = NumberMode.BOX,
            entity_category=EntityCategory.CONFIG,
        ),
        *TIMER_SENSORS,
    ),
    "mk": (
        XTNumberEntityDescription(
            key=DPCode.AUTO_LOCK_TIME,
            translation_key="auto_lock_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.ALARM_TIME,
            translation_key="alarm_time",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "msp": (
        XTNumberEntityDescription(
            key=DPCode.DELAY_CLEAN_TIME,
            translation_key="delay_clean_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.QUIET_TIME_END,
            translation_key="quiet_time_end",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.QUIET_TIME_START,
            translation_key="quiet_time_start",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.SLEEP_START_TIME,
            translation_key="sleep_start_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.SLEEP_END_TIME,
            translation_key="sleep_end_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.UV_START_TIME,
            translation_key="uv_start_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.UV_END_TIME,
            translation_key="uv_end_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.DEO_START_TIME,
            translation_key="deo_start_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.DEO_END_TIME,
            translation_key="deo_end_time",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "mzj": (
        XTNumberEntityDescription(
            key=DPCode.TEMPSET,
            translation_key="temp_set",
            mode = NumberMode.SLIDER,
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.RECIPE,
            translation_key="recipe",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.SETTIME,
            translation_key="set_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.TEMPSC,
            translation_key="tempsc",
            mode = NumberMode.SLIDER,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "qccdz": (
        XTNumberEntityDescription(
            key=DPCode.CHARGE_CUR_SET,
            translation_key="charge_cur_set",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.TIMER_ON,
            translation_key="timer_on",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.SET16A,
            translation_key="set_16a",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=True,
            entity_registry_visible_default=False,
        ),
        XTNumberEntityDescription(
            key=DPCode.SET32A,
            translation_key="set_32a",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=True,
            entity_registry_visible_default=False,
        ),
        XTNumberEntityDescription(
            key=DPCode.SET40A,
            translation_key="set_40a",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=True,
            entity_registry_visible_default=False,
        ),
        XTNumberEntityDescription(
            key=DPCode.SET50A,
            translation_key="set_50a",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=True,
            entity_registry_visible_default=False,
        ),
        *TIMER_SENSORS,
    ),
    "wnykq": (
        XTNumberEntityDescription(
            key=DPCode.BRIGHT_VALUE,
            translation_key="bright_value",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.HUMIDITY_CALIBRATION,
            translation_key="humidity_calibration",
            mode = NumberMode.SLIDER,
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.TEMP_CALIBRATION,
            translation_key="temp_calibration",
            mode = NumberMode.SLIDER,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "ywcgq": (
        XTNumberEntityDescription(
            key=DPCode.MAX_SET,
            translation_key="max_set",
            mode = NumberMode.SLIDER,
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.MINI_SET,
            translation_key="mini_set",
            mode = NumberMode.SLIDER,
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.INSTALLATION_HEIGHT,
            translation_key="installation_height",
            mode = NumberMode.SLIDER,
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=DPCode.LIQUID_DEPTH_MAX,
            translation_key="liquid_depth_max",
            mode = NumberMode.SLIDER,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya number dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    merged_descriptors = NUMBERS
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.NUMBER):
        merged_descriptors = merge_device_descriptors(merged_descriptors, new_descriptor)

    @callback
    def async_discover_device(device_map) -> None:
        """Discover and add a discovered Tuya number."""
        entities: list[XTNumberEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if descriptions := merged_descriptors.get(device.category):
                    entities.extend(
                        XTNumberEntity(device, hass_data.manager, XTNumberEntityDescription(**description.__dict__))
                        for description in descriptions
                        if description.key in device.status
                    )

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors("numbers", merged_descriptors)
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
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description