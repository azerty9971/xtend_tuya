"""Support for Tuya number."""

from __future__ import annotations
from dataclasses import dataclass
from typing import cast
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import EntityCategory, Platform, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.components.number.const import (
    NumberMode,
    DEVICE_CLASS_UNITS as NUMBER_DEVICE_CLASS_UNITS,
)
from .util import (
    restrict_descriptor_category,
)
from .const import (
    TUYA_DISCOVERY_NEW,
    XTDPCode,
    XTMultiManagerPostSetupCallbackPriority,
    LOGGER,
)
from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaNumberEntity,
    TuyaNumberEntityDescription,
    TuyaDPCodeIntegerWrapper,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)
from .smart_cover_control import SmartCoverManager


class XTNumberEntityDescription(TuyaNumberEntityDescription):
    """Describe an Tuya number entity."""

    # Custom native_max_value
    native_max_value: float | None = None

    # duplicate the entity if handled by another integration
    ignore_other_dp_code_handler: bool = False

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTNumberEntityDescription,
        dpcode_wrapper: TuyaDPCodeIntegerWrapper,
    ) -> XTNumberEntity:
        return XTNumberEntity(
            device=device,
            device_manager=device_manager,
            description=XTNumberEntityDescription(**description.__dict__),
            dpcode_wrapper=dpcode_wrapper,
        )


@dataclass
class XTSmartCoverNumberEntityDescription(NumberEntityDescription):
    """Describe a Smart Cover Number entity."""

    control_dp: str | None = None
    force_update: bool = False
    entity_registry_enabled_default: bool = True
    entity_registry_visible_default: bool = True

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSmartCoverNumberEntityDescription,
    ) -> XTSmartCoverNumberEntity:
        return XTSmartCoverNumberEntity(
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
            key=XTDPCode.DEO_END_TIME,
            translation_key="deo_end_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.DEO_START_TIME,
            translation_key="deo_start_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.DELAY_CLEAN_TIME,
            translation_key="delay_clean_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.INDUCTION_DELAY,
            translation_key="induction_delay",
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.INDUCTION_INTERVAL,
            translation_key="induction_interval",
            device_class=NumberDeviceClass.DURATION,
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
            key=XTDPCode.SLEEP_END_TIME,
            translation_key="sleep_end_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.SLEEP_START_TIME,
            translation_key="sleep_start_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.UV_END_TIME,
            translation_key="uv_end_time",
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.UV_START_TIME,
            translation_key="uv_start_time",
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
    # QT-08W Solar Intelligent Water Valve
    "sfkzq": (
        XTNumberEntityDescription(
            key=XTDPCode.COUNTDOWN,
            translation_key="watering_duration",
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
        ),
        XTNumberEntityDescription(
            key=XTDPCode.DELAY_TASK,
            translation_key="rain_snow_delay",
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
            native_max_value=3,
            native_unit_of_measurement="days",
        ),
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
    # Smart Cover timing controls
    "cl": (
        XTSmartCoverNumberEntityDescription(
            key="smart_cover_open_close_time_1",
            translation_key="smart_cover_open_close_time",
            name="Open-Close Time in Seconds",
            icon="mdi:timer",
            native_min_value=1.0,
            native_max_value=300.0,
            native_step=1.0,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
            control_dp=XTDPCode.CONTROL,
        ),
        XTSmartCoverNumberEntityDescription(
            key="smart_cover_open_close_time_2",
            translation_key="smart_cover_open_close_time_2",
            name="Open-Close Time 2 in Seconds",
            icon="mdi:timer",
            native_min_value=1.0,
            native_max_value=300.0,
            native_step=1.0,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
            control_dp=XTDPCode.CONTROL_2,
        ),
        XTSmartCoverNumberEntityDescription(
            key="smart_cover_open_close_time_3",
            translation_key="smart_cover_open_close_time_3",
            name="Open-Close Time 3 in Seconds",
            icon="mdi:timer",
            native_min_value=1.0,
            native_max_value=300.0,
            native_step=1.0,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
            control_dp=XTDPCode.CONTROL_3,
        ),
    ),
    "clkg": (
        XTSmartCoverNumberEntityDescription(
            key="smart_cover_open_close_time_1",
            translation_key="smart_cover_open_close_time",
            name="Open-Close Time in Seconds",
            icon="mdi:timer",
            native_min_value=1.0,
            native_max_value=300.0,
            native_step=1.0,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
            control_dp=XTDPCode.CONTROL,
        ),
        XTSmartCoverNumberEntityDescription(
            key="smart_cover_open_close_time_2",
            translation_key="smart_cover_open_close_time_2",
            name="Open-Close Time 2 in Seconds",
            icon="mdi:timer",
            native_min_value=1.0,
            native_max_value=300.0,
            native_step=1.0,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
            control_dp=XTDPCode.CONTROL_2,
        ),
        XTSmartCoverNumberEntityDescription(
            key="smart_cover_open_close_time_3",
            translation_key="smart_cover_open_close_time_3",
            name="Open-Close Time 3 in Seconds",
            icon="mdi:timer",
            native_min_value=1.0,
            native_max_value=300.0,
            native_step=1.0,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            device_class=NumberDeviceClass.DURATION,
            entity_category=EntityCategory.CONFIG,
            control_dp=XTDPCode.CONTROL_3,
        ),
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
    this_platform = Platform.NUMBER

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    # Initialize smart cover manager if not exists
    if not hasattr(hass_data.manager, 'smart_cover_manager'):
        hass_data.manager.smart_cover_manager = SmartCoverManager(hass)

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, tuple[XTNumberEntityDescription, ...]],
            dict[str, tuple[XTNumberEntityDescription, ...]],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            NUMBERS,
            entry.runtime_data.multi_manager,
            XTNumberEntityDescription,
            this_platform,
        ),
    )

    @callback
    def async_add_generic_entities(device_map) -> None:
        if hass_data.manager is None:
            return
        entities: list[XTNumberEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                generic_dpcodes = XTEntity.get_generic_dpcodes_for_this_platform(
                    device, this_platform
                )
                if not generic_dpcodes:
                    continue
                dev_class_from_uom = XTEntity.get_device_classes_from_uom(NUMBER_DEVICE_CLASS_UNITS)
                for dpcode in generic_dpcodes:
                    dpcode_info = device.get_dpcode_information(dpcode=dpcode)
                    descriptor = XTNumberEntityDescription(
                        key=dpcode,
                        device_class=XTEntity.get_device_class_from_uom(dpcode_info, dev_class_from_uom, device),
                        translation_key="xt_generic_number",
                        translation_placeholders={
                            "name": XTEntity.get_human_name(dpcode)
                        },
                        entity_registry_enabled_default=False,
                        entity_registry_visible_default=False,
                    )
                    if dpcode_wrapper := TuyaDPCodeIntegerWrapper.find_dpcode(
                        device, descriptor.key, prefer_function=True
                    ):
                        entities.append(
                            XTNumberEntity.get_entity_instance(
                                descriptor, device, hass_data.manager, dpcode_wrapper
                            )
                        )
        async_add_entities(entities)

    created_smart_cover_ids: set[str] = set()

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered Tuya number."""
        if hass_data.manager is None:
            return
        entities: list[XTNumberEntity | XTSmartCoverNumberEntity] = []
        device_ids = [*device_map]
        # Handle smart cover number entities for cl/clkg devices
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if device.category in ["cl", "clkg"]:
                    smart_cover_descs = NUMBERS.get(device.category)
                    if smart_cover_descs:
                        for desc in smart_cover_descs:
                            if isinstance(desc, XTSmartCoverNumberEntityDescription):
                                if desc.control_dp and (
                                    desc.control_dp in device.status_range
                                    or desc.control_dp in device.function
                                ):
                                    entity_uid = f"{device.id}_{desc.control_dp}_{desc.key}"
                                    if entity_uid not in created_smart_cover_ids:
                                        created_smart_cover_ids.add(entity_uid)
                                        entities.append(
                                            XTSmartCoverNumberEntity.get_entity_instance(
                                                desc, device, hass_data.manager
                                            )
                                        )
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
                            tuple[XTNumberEntityDescription, ...],
                            restrict_descriptor_category(
                                category_descriptions, [restrict_dpcode]
                            ),
                        )
                    entities.extend(
                        XTNumberEntity.get_entity_instance(
                            description, device, hass_data.manager, dpcode_wrapper
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
                                dpcode_wrapper := TuyaDPCodeIntegerWrapper.find_dpcode(
                                    device, description.key, prefer_function=True
                                )
                            )
                        )
                    )
                    entities.extend(
                        XTNumberEntity.get_entity_instance(
                            description, device, hass_data.manager, dpcode_wrapper
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
                                dpcode_wrapper := TuyaDPCodeIntegerWrapper.find_dpcode(
                                    device, description.key, prefer_function=True
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


class XTNumberEntity(XTEntity, TuyaNumberEntity):
    """XT Number Entity."""

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTNumberEntityDescription,
        dpcode_wrapper: TuyaDPCodeIntegerWrapper,
    ) -> None:
        """Init XT number."""
        super(XTNumberEntity, self).__init__(
            device, device_manager, description, dpcode_wrapper=dpcode_wrapper
        )
        super(XTEntity, self).__init__(
            device,
            device_manager,  # type: ignore
            description,
            dpcode_wrapper,
        )
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description
        # Use custom native_max_value
        if description.native_max_value is not None:
            self._attr_native_max_value = description.native_max_value

    @staticmethod
    def get_entity_instance(
        description: XTNumberEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
        dpcode_wrapper: TuyaDPCodeIntegerWrapper,
    ) -> XTNumberEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(
                device, device_manager, description, dpcode_wrapper
            )
        return XTNumberEntity(
            device,
            device_manager,
            XTNumberEntityDescription(**description.__dict__),
            dpcode_wrapper,
        )


class XTSmartCoverNumberEntity(XTEntity, RestoreEntity, NumberEntity):
    """XT Smart Cover Number Entity for timing configuration."""

    entity_description: XTSmartCoverNumberEntityDescription

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSmartCoverNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description

        base_name = "Open-Close Time in Seconds"
        if description.control_dp == XTDPCode.CONTROL_2:
            base_name = "Open-Close Time 2 in Seconds"
        elif description.control_dp == XTDPCode.CONTROL_3:
            base_name = "Open-Close Time 3 in Seconds"

        self.entity_description.name = base_name
        super().__init__(device, device_manager, description)
        self._attr_native_value = 60.0

    @property
    def unique_id(self) -> str:
        """Return unique ID for the entity."""
        return f"{self.device.id}_{self.entity_description.control_dp}_{self.entity_description.key}"

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self._attr_native_value

    async def async_set_native_value(self, value: float) -> None:
        """Set the timing value."""
        self._attr_native_value = value

        if hasattr(self.device_manager, 'smart_cover_manager'):
            controller = self.device_manager.smart_cover_manager.get_controller(
                self.device.id, self.entity_description.control_dp
            )
            if not controller:
                cover_entity_id = f"cover.{self.device.name.lower().replace(' ', '_')}"
                controller = self.device_manager.smart_cover_manager.register_cover(
                    self.device,
                    self.device_manager,
                    cover_entity_id,
                    self.entity_description.control_dp,
                )
            if controller:
                controller.set_timing_config(value, value)

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Entity added to hass."""
        await super().async_added_to_hass()

        restored_from_controller = False

        # FIRST: Try to read directly from storage file
        try:
            import json
            import os
            storage_key = f"xtend_tuya_smart_cover_{self.device.id}_{self.entity_description.control_dp}"
            storage_path = self.hass.config.path(f".storage/{storage_key}")

            def _read_storage():
                if os.path.exists(storage_path):
                    with open(storage_path, 'r') as f:
                        return json.load(f)
                return None

            storage_data = await self.hass.async_add_executor_job(_read_storage)
            if storage_data:
                timing_config = storage_data.get("data", {}).get("timing_config", {})
                storage_value = timing_config.get("full_open_time")

                if storage_value and storage_value != 60.0 and storage_value >= 1.0:
                    self._attr_native_value = storage_value
                    restored_from_controller = True

                    if hasattr(self.device_manager, 'smart_cover_manager'):
                        controller = self.device_manager.smart_cover_manager.get_controller(
                            self.device.id, self.entity_description.control_dp
                        )
                        if controller:
                            controller.set_timing_config(storage_value, storage_value)
        except Exception:
            pass

        # SECOND: Try to get value from controller
        if not restored_from_controller and hasattr(self.device_manager, 'smart_cover_manager'):
            controller = self.device_manager.smart_cover_manager.get_controller(
                self.device.id, self.entity_description.control_dp
            )
            if controller and hasattr(controller, 'timing_config'):
                controller_value = controller.timing_config.full_open_time
                if controller_value != 60.0 and controller_value >= 1.0:
                    self._attr_native_value = controller_value
                    restored_from_controller = True

        # THIRD: Fall back to HA state
        if not restored_from_controller:
            last_state = await self.async_get_last_state()
            if last_state is not None and last_state.state not in ("unknown", "unavailable"):
                try:
                    restored_value = float(last_state.state)
                    if (self.native_min_value is None or restored_value >= self.native_min_value) and \
                       (self.native_max_value is None or restored_value <= self.native_max_value):
                        self._attr_native_value = restored_value

                        if hasattr(self.device_manager, 'smart_cover_manager'):
                            controller = self.device_manager.smart_cover_manager.get_controller(
                                self.device.id, self.entity_description.control_dp
                            )
                            if not controller:
                                cover_entity_id = f"cover.{self.device.name.lower().replace(' ', '_')}"
                                controller = self.device_manager.smart_cover_manager.register_cover(
                                    self.device,
                                    self.device_manager,
                                    cover_entity_id,
                                    self.entity_description.control_dp,
                                )
                            if controller:
                                controller.set_timing_config(restored_value, restored_value)
                except (ValueError, TypeError):
                    self._attr_native_value = 60.0

        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.entity_description.control_dp in self.device.status_range
            or self.entity_description.control_dp in self.device.function
        )

    @staticmethod
    def get_entity_instance(
        description: XTSmartCoverNumberEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
    ) -> XTSmartCoverNumberEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(device, device_manager, description)
        return XTSmartCoverNumberEntity(device, device_manager, description)
