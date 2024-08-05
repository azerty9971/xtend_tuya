"""Constants for the Tuya integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum, IntFlag
import logging

from tuya_iot import TuyaCloudOpenAPIEndpoint

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    Platform,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolume,
)

DOMAIN = "xtend_tuya"
DOMAIN_ORIG = "tuya"
LOGGER = logging.getLogger(__package__)

CONF_APP_TYPE = "tuya_app_type"
CONF_ENDPOINT = "endpoint"
CONF_TERMINAL_ID = "terminal_id"
CONF_TOKEN_INFO = "token_info"
CONF_USER_CODE = "user_code"
CONF_USERNAME = "username"
#OpenTuya specific conf
CONF_ENDPOINT_OT = "endpoint"
CONF_AUTH_TYPE = "auth_type"
CONF_ACCESS_ID = "access_id"
CONF_ACCESS_SECRET = "access_secret"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_COUNTRY_CODE = "country_code"
CONF_APP_TYPE = "tuya_app_type"

TUYA_CLIENT_ID = "HA_3y9q4ak7g4ephrvke"
TUYA_SCHEMA = "haauthorize"

TUYA_DISCOVERY_NEW_ORIG = "tuya_discovery_new"
TUYA_HA_SIGNAL_UPDATE_ENTITY_ORIG = "tuya_entry_update"
TUYA_DISCOVERY_NEW = "xt_tuya_discovery_new"
TUYA_HA_SIGNAL_UPDATE_ENTITY = "xt_tuya_entry_update"

TUYA_RESPONSE_CODE = "code"
TUYA_RESPONSE_MSG = "msg"
TUYA_RESPONSE_QR_CODE = "qrcode"
TUYA_RESPONSE_RESULT = "result"
TUYA_RESPONSE_SUCCESS = "success"
#OpenTuya specific
TUYA_RESPONSE_PLATFORM_URL = "platform_url"
TUYA_SMART_APP = "tuyaSmart"
SMARTLIFE_APP = "smartlife"

MESSAGE_SOURCE_TUYA_IOT = "tuya_iot"
MESSAGE_SOURCE_TUYA_SHARING = "tuya_sharing"

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.FAN,
    Platform.HUMIDIFIER,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SCENE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
    Platform.VACUUM,
]

class VirtualStates(IntFlag):
    """Virtual states"""
    STATE_COPY_TO_MULTIPLE_STATE_NAME           = 0X0001,   #Copy the state so that it can be used with other virtual states
    STATE_SUMMED_IN_REPORTING_PAYLOAD           = 0X0002,   #Spoof the state value to make it a total instead of an incremental value

class VirtualFunctions(IntFlag):
    """Virtual functions"""
    FUNCTION_RESET_STATE                        = 0X0001,   #Reset the specified states

@dataclass
class DescriptionVirtualState:
    """Describes the VirtualStates linked to a specific Description Key."""
    
    key: str
    virtual_state_name: str
    virtual_state_value: VirtualStates = None
    vs_copy_to_state: list[DPCode] = field(default_factory=list)

@dataclass
class DescriptionVirtualFunction:
    """Describes the VirtualFunctions linked to a specific Description Key."""
    
    key: str
    virtual_function_name: str
    virtual_function_value: VirtualStates = None
    vf_reset_state: list[DPCode] = field(default_factory=list)

class WorkMode(StrEnum):
    """Work modes."""

    COLOUR = "colour"
    MUSIC = "music"
    SCENE = "scene"
    WHITE = "white"


class DPType(StrEnum):
    """Data point types."""

    BOOLEAN = "Boolean"
    ENUM = "Enum"
    INTEGER = "Integer"
    JSON = "Json"
    RAW = "Raw"
    STRING = "String"


class DPCode(StrEnum):
    """Data Point Codes used by Tuya.

    https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
    """

    ADD_ELE = "add_ele" #Added watt since last heartbeat
    ADD_ELE2 = "add_ele2" #Added watt since last heartbeat
    AIR_QUALITY = "air_quality"
    ALARM_LOCK = "alarm_lock"
    ALARM_SWITCH = "alarm_switch"  # Alarm switch
    ALARM_TIME = "alarm_time"  # Alarm time
    ALARM_VOLUME = "alarm_volume"  # Alarm volume
    ALARM_MESSAGE = "alarm_message"
    ANGLE_HORIZONTAL = "angle_horizontal"
    ANGLE_VERTICAL = "angle_vertical"
    ANION = "anion"  # Ionizer unit
    ARM_DOWN_PERCENT = "arm_down_percent"
    ARM_UP_PERCENT = "arm_up_percent"
    AUTO_CLEAN = "auto_clean"
    AUTO_DEORDRIZER = "auto_deordrizer"
    AUTO_LOCK_TIME = "auto_lock_time"
    AUTOMATIC_LOCK = "automatic_lock"
    BALANCE_ENERGY = "balance_energy"
    BASIC_ANTI_FLICKER = "basic_anti_flicker"
    BASIC_DEVICE_VOLUME = "basic_device_volume"
    BASIC_FLIP = "basic_flip"
    BASIC_INDICATOR = "basic_indicator"
    BASIC_NIGHTVISION = "basic_nightvision"
    BASIC_OSD = "basic_osd"
    BASIC_PRIVATE = "basic_private"
    BASIC_WDR = "basic_wdr"
    BATTERY = "battery"  # Used by non-standard contact sensor implementations
    BATTERY_PERCENTAGE = "battery_percentage"  # Battery percentage
    BATTERY_STATE = "battery_state"  # Battery state
    BATTERY_VALUE = "battery_value"  # Battery value
    BEEP = "beep"
    BEEP_VOLUME = "beep_volume"
    BRIGHT_CONTROLLER = "bright_controller"
    BRIGHT_STATE = "bright_state"  # Brightness status
    BRIGHT_VALUE = "bright_value"  # Brightness
    BRIGHT_VALUE_1 = "bright_value_1"
    BRIGHT_VALUE_2 = "bright_value_2"
    BRIGHT_VALUE_3 = "bright_value_3"
    BRIGHT_VALUE_V2 = "bright_value_v2"
    BRIGHTNESS_MAX_1 = "brightness_max_1"
    BRIGHTNESS_MAX_2 = "brightness_max_2"
    BRIGHTNESS_MAX_3 = "brightness_max_3"
    BRIGHTNESS_MIN_1 = "brightness_min_1"
    BRIGHTNESS_MIN_2 = "brightness_min_2"
    BRIGHTNESS_MIN_3 = "brightness_min_3"
    C_F = "c_f"  # Temperature unit switching
    CALIBRATION = "calibration"
    CAPACITY_CALIBRATION = "capacity_calibration"
    CAT_WEIGHT = "cat_weight"
    CH2O_STATE = "ch2o_state"
    CH2O_VALUE = "ch2o_value"
    CH4_SENSOR_STATE = "ch4_sensor_state"
    CH4_SENSOR_VALUE = "ch4_sensor_value"
    CHARGE_ENERGY = "charge_energy"
    CHILD_LOCK = "child_lock"  # Child lock
    CISTERN = "cistern"
    CLEAN = "clean"
    CLEAN_AREA = "clean_area"
    CLEAN_NOTICE = "Clean_notice"
    CLEAN_TASTE = "Clean_taste"
    CLEAN_TASTE_SWITCH = "Clean_tasteSwitch"
    CLEAN_TIME = "clean_time"
    CLEAN_TIME_SWITCH = "clean_time_switch"
    CLEANING = "cleaning"
    CLEANING_NUM = "cleaning_num"
    CLICK_SUSTAIN_TIME = "click_sustain_time"
    CLOUD_RECIPE_NUMBER = "cloud_recipe_number"
    CLOSED_OPENED = "closed_opened"
    CLOSED_OPENED_KIT = "closed_opened_kit"
    CO_STATE = "co_state"
    CO_STATUS = "co_status"
    CO_VALUE = "co_value"
    CO2_STATE = "co2_state"
    CO2_VALUE = "co2_value"  # CO2 concentration
    COLLECTION_MODE = "collection_mode"
    COLOR_DATA_V2 = "color_data_v2"
    COLOUR_DATA = "colour_data"  # Colored light mode
    COLOUR_DATA_HSV = "colour_data_hsv"  # Colored light mode
    COLOUR_DATA_V2 = "colour_data_v2"  # Colored light mode
    COOK_TEMPERATURE = "cook_temperature"
    COOK_TIME = "cook_time"
    CONCENTRATION_SET = "concentration_set"  # Concentration setting
    CONTROL = "control"
    CONTROL_2 = "control_2"
    CONTROL_3 = "control_3"
    CONTROL_BACK = "control_back"
    CONTROL_BACK_MODE = "control_back_mode"
    COUNTDOWN = "countdown"  # Countdown
    COUNTDOWN_LEFT = "countdown_left"
    COUNTDOWN_SET = "countdown_set"  # Countdown setting
    CRY_DETECTION_SWITCH = "cry_detection_switch"
    CUP_NUMBER = "cup_number"  # NUmber of cups
    CUR_CURRENT = "cur_current"  # Actual current
    CUR_POWER = "cur_power"  # Actual power
    CUR_VOLTAGE = "cur_voltage"  # Actual voltage
    DECIBEL_SENSITIVITY = "decibel_sensitivity"
    DECIBEL_SWITCH = "decibel_switch"
    DEHUMIDITY_SET_ENUM = "dehumidify_set_enum"
    DEHUMIDITY_SET_VALUE = "dehumidify_set_value"
    DELAY_CLEAN_TIME = "delay_clean_time"
    DEODORIZATION = "deodorization"
    DEODORIZATION_NUM = "deodorization_num"
    DEO_START_TIME = "deo_start_time"
    DEO_END_TIME = "deo_end_time"
    DETECTION_SENSITIVITY = "detection_sensitivity"
    DISINFECTION = "disinfection"
    DO_NOT_DISTURB = "do_not_disturb"
    DOORCONTACT_STATE = "doorcontact_state"  # Status of door window sensor
    DOORCONTACT_STATE_2 = "doorcontact_state_2"
    DOORCONTACT_STATE_3 = "doorcontact_state_3"
    DUSTER_CLOTH = "duster_cloth"
    ECO2 = "eco2"
    EDGE_BRUSH = "edge_brush"
    ELECTRICITY_LEFT = "electricity_left"
    EMPTY = "empty"
    EXCRETION_TIME_DAY = "excretion_time_day"
    EXCRETION_TIMES_DAY = "excretion_times_day"
    FACTORY_RESET = "factory_reset"
    FAN_BEEP = "fan_beep"  # Sound
    FAN_COOL = "fan_cool"  # Cool wind
    FAN_DIRECTION = "fan_direction"  # Fan direction
    FAN_HORIZONTAL = "fan_horizontal"  # Horizontal swing flap angle
    FAN_SPEED = "fan_speed"
    FAN_SPEED_ENUM = "fan_speed_enum"  # Speed mode
    FAN_SPEED_PERCENT = "fan_speed_percent"  # Stepless speed
    FAN_SWITCH = "fan_switch"
    FAN_MODE = "fan_mode"
    FAN_VERTICAL = "fan_vertical"  # Vertical swing flap angle
    FAR_DETECTION = "far_detection"
    FAULT = "fault"
    FEED_REPORT = "feed_report"
    FEED_STATE = "feed_state"
    FILTER = "filter"
    FILTER_LIFE = "filter"
    FILTER_RESET = "filter_reset"  # Filter (cartridge) reset
    FLOODLIGHT_LIGHTNESS = "floodlight_lightness"
    FLOODLIGHT_SWITCH = "floodlight_switch"
    FORWARD_ENERGY_TOTAL = "forward_energy_total"
    GAS_SENSOR_STATE = "gas_sensor_state"
    GAS_SENSOR_STATUS = "gas_sensor_status"
    GAS_SENSOR_VALUE = "gas_sensor_value"
    HISTORY = "History"
    HUMIDIFIER = "humidifier"  # Humidification
    HUMIDITY = "humidity"  # Humidity
    HUMIDITY_CURRENT = "humidity_current"  # Current humidity
    HUMIDITY_INDOOR = "humidity_indoor"  # Indoor humidity
    HUMIDITY_SET = "humidity_set"  # Humidity setting
    HUMIDITY_VALUE = "humidity_value"  # Humidity
    INDICATOR_LIGHT = "indicator_light"
    INDUCTION_CLEAN = "Induction_Clean"
    INDUCTION_DELAY = "induction_delay"
    INDUCTION_INTERVAL = "induction_interval"
    IPC_WORK_MODE = "ipc_work_mode"
    KILL = "kill"
    LED_TYPE_1 = "led_type_1"
    LED_TYPE_2 = "led_type_2"
    LED_TYPE_3 = "led_type_3"
    LEVEL = "level"
    LEVEL_CURRENT = "level_current"
    LIGHT = "light"  # Light
    LIGHT_MODE = "light_mode"
    LOCK = "lock"  # Lock / Child lock
    MASTER_MODE = "master_mode"  # alarm mode
    MACH_OPERATE = "mach_operate"
    MAGNETNUM = "magnetNum"
    MANUAL_CLEAN = "manual_clean"
    MANUAL_FEED = "manual_feed"
    MANUAL_LOCK = "manual_lock"
    MATERIAL = "material"  # Material
    MONITORING = "monitoring"
    MODE = "mode"  # Working mode / Mode
    MOODLIGHTING = "moodlighting"  # Mood light
    MOTION_RECORD = "motion_record"
    MOTION_SENSITIVITY = "motion_sensitivity"
    MOTION_SWITCH = "motion_switch"  # Motion switch
    MOTION_TRACKING = "motion_tracking"
    MOVEMENT_DETECT_PIC = "movement_detect_pic"
    MUFFLING = "muffling"  # Muffling
    M_ADC_NUM = "M_ADC_NUM"
    NEAR_DETECTION = "near_detection"
    NET_NOTICE = "Net_notice"
    NOTIFICATION_STATUS = "notification_status"
    NOT_DISTURB = "not_disturb"
    NOT_DISTURB_SWITCH = "not_disturb_Switch"
    NUMBER = "number"
    ODOURLESS = "odourless"
    OPPOSITE = "opposite"
    OXYGEN = "oxygen"  # Oxygen bar
    PAUSE = "pause"
    PEDAL_ANGLE = "pedal_angle"
    PERCENT_CONTROL = "percent_control"
    PERCENT_CONTROL_2 = "percent_control_2"
    PERCENT_CONTROL_3 = "percent_control_3"
    PERCENT_STATE = "percent_state"
    PERCENT_STATE_2 = "percent_state_2"
    PERCENT_STATE_3 = "percent_state_3"
    PHASE_A = "phase_a"
    PHASE_B = "phase_b"
    PHASE_C = "phase_c"
    PIR = "pir"  # Motion sensor
    PIR_RADAR = "PIR_RADAR"
    PM1 = "pm1"
    PM10 = "pm10"
    PM25 = "pm25"
    PM25_STATE = "pm25_state"
    PM25_VALUE = "pm25_value"
    POSITION = "position"
    POWDER_SET = "powder_set"  # Powder
    POWER = "power"
    POWER_GO = "power_go"
    PRESENCE_STATE = "presence_state"
    PRESSURE_STATE = "pressure_state"
    PRESSURE_VALUE = "pressure_value"
    PUMP_RESET = "pump_reset"  # Water pump reset
    QUIET_TIMING_ON = "quiet_timing_on"
    QUIET_TIME_END = "quiet_time_end"
    QUIET_TIME_START = "quiet_time_start"
    REBOOT = "reboot"
    RECORD_MODE = "record_mode"
    RECORD_SWITCH = "record_switch"  # Recording switch
    RELAY_STATUS = "relay_status"
    REMAIN_TIME = "remain_time"
    RESET_ADD_ELE = "reset_add_ele"
    RESET_DUSTER_CLOTH = "reset_duster_cloth"
    RESET_EDGE_BRUSH = "reset_edge_brush"
    RESET_FILTER = "reset_filter"
    RESET_MAP = "reset_map"
    RESET_ROLL_BRUSH = "reset_roll_brush"
    ROLL_BRUSH = "roll_brush"
    RTC_TIME = "rtc_time"
    SAND_SURFACE_CALIBRATION = "sand_surface_calibration"
    SEEK = "seek"
    SENSITIVITY = "sensitivity"  # Sensitivity
    SENSOR_HUMIDITY = "sensor_humidity"
    SENSOR_TEMPERATURE = "sensor_temperature"
    SHAKE = "shake"  # Oscillating
    SHOCK_STATE = "shock_state"  # Vibration status
    SIREN_SWITCH = "siren_switch"
    SITUATION_SET = "situation_set"
    SLEEP = "sleep"  # Sleep function
    SLEEPING = "sleeping"
    SLEEP_START_TIME = "sleep_start_time"
    SLEEP_END_TIME = "sleep_end_time"
    SLOW_FEED = "slow_feed"
    SMART_CLEAN = "smart_clean"
    SMOKE_SENSOR_STATE = "smoke_sensor_state"
    SMOKE_SENSOR_STATUS = "smoke_sensor_status"
    SMOKE_SENSOR_VALUE = "smoke_sensor_value"
    SOS = "sos"  # Emergency State
    SOS_STATE = "sos_state"  # Emergency mode
    SOUND_MODE = "sound_mode"
    SPECIAL_FUNCTION = "special_function"
    SPEED = "speed"  # Speed level
    SPRAY_MODE = "spray_mode"  # Spraying mode
    START = "start"  # Start
    STATUS = "status"
    STERILIZATION = "sterilization"  # Sterilization
    STORE_FULL_NOTIFY = "store_full_notify"
    SUCTION = "suction"
    SWING = "swing"  # Swing mode
    SWITCH = "switch"  # Switch
    SWITCH_1 = "switch_1"  # Switch 1
    SWITCH_2 = "switch_2"  # Switch 2
    SWITCH_3 = "switch_3"  # Switch 3
    SWITCH_4 = "switch_4"  # Switch 4
    SWITCH_5 = "switch_5"  # Switch 5
    SWITCH_6 = "switch_6"  # Switch 6
    SWITCH_7 = "switch_7"  # Switch 7
    SWITCH_8 = "switch_8"  # Switch 8
    SWITCH_BACKLIGHT = "switch_backlight"  # Backlight switch
    SWITCH_CHARGE = "switch_charge"
    SWITCH_CONTROLLER = "switch_controller"
    SWITCH_DISTURB = "switch_disturb"
    SWITCH_FAN = "switch_fan"
    SWITCH_HORIZONTAL = "switch_horizontal"  # Horizontal swing flap switch
    SWITCH_LED = "switch_led"  # Switch
    SWITCH_LED_1 = "switch_led_1"
    SWITCH_LED_2 = "switch_led_2"
    SWITCH_LED_3 = "switch_led_3"
    SWITCH_NIGHT_LIGHT = "switch_night_light"
    SWITCH_SAVE_ENERGY = "switch_save_energy"
    SWITCH_SOUND = "switch_sound"  # Voice switch
    SWITCH_SPRAY = "switch_spray"  # Spraying switch
    SWITCH_USB1 = "switch_usb1"  # USB 1
    SWITCH_USB2 = "switch_usb2"  # USB 2
    SWITCH_USB3 = "switch_usb3"  # USB 3
    SWITCH_USB4 = "switch_usb4"  # USB 4
    SWITCH_USB5 = "switch_usb5"  # USB 5
    SWITCH_USB6 = "switch_usb6"  # USB 6
    SWITCH_VERTICAL = "switch_vertical"  # Vertical swing flap switch
    SWITCH_VOICE = "switch_voice"  # Voice switch
    TEMP = "temp"  # Temperature setting
    TEMPERATURE = "temperature"
    TEMPER_ALARM = "temper_alarm"  # Tamper alarm
    TEMP_ADC = "temp_adc"
    TEMP_BOILING_C = "temp_boiling_c"
    TEMP_BOILING_F = "temp_boiling_f"
    TEMP_CONTROLLER = "temp_controller"
    TEMP_CURRENT = "temp_current"  # Current temperature in °C
    TEMP_CURRENT_F = "temp_current_f"  # Current temperature in °F
    TEMP_INDOOR = "temp_indoor"  # Indoor temperature in °C
    TEMP_SET = "temp_set"  # Set the temperature in °C
    TEMP_SET_F = "temp_set_f"  # Set the temperature in °F
    TEMP_UNIT_CONVERT = "temp_unit_convert"  # Temperature unit switching
    TEMP_VALUE = "temp_value"  # Color temperature
    TEMP_VALUE_V2 = "temp_value_v2"
    TIME_TOTAL = "time_total"
    TOILET_NOTICE = "toilet_notice"
    TIME_USE = "time_use"  # Total seconds of irrigation
    TOTAL_CLEAN_AREA = "total_clean_area"
    TOTAL_CLEAN_COUNT = "total_clean_count"
    TOTAL_CLEAN_TIME = "total_clean_time"
    TOTAL_FORWARD_ENERGY = "total_forward_energy"
    TOTAL_TIME = "total_time"
    TOTAL_PM = "total_pm"
    TRASH_STATUS = "trash_status"
    TVOC = "tvoc"
    UNIT = "unit"
    UPPER_TEMP = "upper_temp"
    UPPER_TEMP_F = "upper_temp_f"
    USAGE_TIMES = "usage_times"
    UV = "uv"  # UV sterilization
    UV_START_TIME = "uv_start_time"
    UV_END_TIME = "uv_end_time"
    VA_BATTERY = "va_battery"
    VA_HUMIDITY = "va_humidity"
    VA_TEMPERATURE = "va_temperature"
    VOC_STATE = "voc_state"
    VOC_VALUE = "voc_value"
    VOICE_SWITCH = "voice_switch"
    VOICE_TIMES = "voice_times"
    VOLUME_SET = "volume_set"
    WARM = "warm"  # Heat preservation
    WARM_TIME = "warm_time"  # Heat preservation time
    WATER = "water"
    WATER_RESET = "water_reset"  # Resetting of water usage days
    WATER_SET = "water_set"  # Water level
    WATERSENSOR_STATE = "watersensor_state"
    WEATHER_DELAY = "weather_delay"
    WET = "wet"  # Humidification
    WINDOW_CHECK = "window_check"
    WINDOW_STATE = "window_state"
    WINDSPEED = "windspeed"
    WIRELESS_BATTERYLOCK = "wireless_batterylock"
    WIRELESS_ELECTRICITY = "wireless_electricity"
    WORK_MODE = "work_mode"  # Working mode
    WORK_POWER = "work_power"
    WORK_STAT = "work_stat"


@dataclass
class UnitOfMeasurement:
    """Describes a unit of measurement."""

    unit: str
    device_classes: set[str]

    aliases: set[str] = field(default_factory=set)
    conversion_unit: str | None = None
    conversion_fn: Callable[[float], float] | None = None


# A tuple of available units of measurements we can work with.
# Tuya's devices aren't consistent in UOM use, thus this provides
# a list of aliases for units and possible conversions we can do
# to make them compatible with our model.
UNITS = (
    UnitOfMeasurement(
        unit="",
        aliases={" "},
        device_classes={
            SensorDeviceClass.AQI,
            SensorDeviceClass.DATE,
            SensorDeviceClass.MONETARY,
            SensorDeviceClass.TIMESTAMP,
        },
    ),
    UnitOfMeasurement(
        unit=PERCENTAGE,
        aliases={"pct", "percent", "% RH"},
        device_classes={
            SensorDeviceClass.BATTERY,
            SensorDeviceClass.HUMIDITY,
            SensorDeviceClass.POWER_FACTOR,
        },
    ),
    UnitOfMeasurement(
        unit=CONCENTRATION_PARTS_PER_MILLION,
        device_classes={
            SensorDeviceClass.CO,
            SensorDeviceClass.CO2,
        },
    ),
    UnitOfMeasurement(
        unit=CONCENTRATION_PARTS_PER_BILLION,
        device_classes={
            SensorDeviceClass.CO,
            SensorDeviceClass.CO2,
        },
        conversion_unit=CONCENTRATION_PARTS_PER_MILLION,
        conversion_fn=lambda x: x / 1000,
    ),
    UnitOfMeasurement(
        unit=UnitOfElectricCurrent.AMPERE,
        aliases={"a", "ampere"},
        device_classes={SensorDeviceClass.CURRENT},
    ),
    UnitOfMeasurement(
        unit=UnitOfElectricCurrent.MILLIAMPERE,
        aliases={"ma", "milliampere"},
        device_classes={SensorDeviceClass.CURRENT},
        conversion_unit=UnitOfElectricCurrent.AMPERE,
        conversion_fn=lambda x: x / 1000,
    ),
    UnitOfMeasurement(
        unit=UnitOfEnergy.WATT_HOUR,
        aliases={"wh", "watthour"},
        device_classes={SensorDeviceClass.ENERGY},
    ),
    UnitOfMeasurement(
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        aliases={"kwh", "kilowatt-hour", "kW·h"},
        device_classes={SensorDeviceClass.ENERGY},
    ),
    UnitOfMeasurement(
        unit=UnitOfVolume.CUBIC_FEET,
        aliases={"ft3"},
        device_classes={SensorDeviceClass.GAS},
    ),
    UnitOfMeasurement(
        unit=UnitOfVolume.CUBIC_METERS,
        aliases={"m3"},
        device_classes={SensorDeviceClass.GAS},
    ),
    UnitOfMeasurement(
        unit=LIGHT_LUX,
        aliases={"lux"},
        device_classes={SensorDeviceClass.ILLUMINANCE},
    ),
    UnitOfMeasurement(
        unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        aliases={"ug/m3", "µg/m3", "ug/m³"},
        device_classes={
            SensorDeviceClass.NITROGEN_DIOXIDE,
            SensorDeviceClass.NITROGEN_MONOXIDE,
            SensorDeviceClass.NITROUS_OXIDE,
            SensorDeviceClass.OZONE,
            SensorDeviceClass.PM1,
            SensorDeviceClass.PM25,
            SensorDeviceClass.PM10,
            SensorDeviceClass.SULPHUR_DIOXIDE,
            SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        },
    ),
    UnitOfMeasurement(
        unit=CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
        aliases={"mg/m3"},
        device_classes={
            SensorDeviceClass.NITROGEN_DIOXIDE,
            SensorDeviceClass.NITROGEN_MONOXIDE,
            SensorDeviceClass.NITROUS_OXIDE,
            SensorDeviceClass.OZONE,
            SensorDeviceClass.PM1,
            SensorDeviceClass.PM25,
            SensorDeviceClass.PM10,
            SensorDeviceClass.SULPHUR_DIOXIDE,
            SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        },
        conversion_unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        conversion_fn=lambda x: x * 1000,
    ),
    UnitOfMeasurement(
        unit=UnitOfPower.WATT,
        aliases={"watt"},
        device_classes={SensorDeviceClass.POWER},
    ),
    UnitOfMeasurement(
        unit=UnitOfPower.KILO_WATT,
        aliases={"kilowatt"},
        device_classes={SensorDeviceClass.POWER},
    ),
    UnitOfMeasurement(
        unit=UnitOfPressure.BAR,
        device_classes={SensorDeviceClass.PRESSURE},
    ),
    UnitOfMeasurement(
        unit=UnitOfPressure.MBAR,
        aliases={"millibar"},
        device_classes={SensorDeviceClass.PRESSURE},
    ),
    UnitOfMeasurement(
        unit=UnitOfPressure.HPA,
        aliases={"hpa", "hectopascal"},
        device_classes={SensorDeviceClass.PRESSURE},
    ),
    UnitOfMeasurement(
        unit=UnitOfPressure.INHG,
        aliases={"inhg"},
        device_classes={SensorDeviceClass.PRESSURE},
    ),
    UnitOfMeasurement(
        unit=UnitOfPressure.PSI,
        device_classes={SensorDeviceClass.PRESSURE},
    ),
    UnitOfMeasurement(
        unit=UnitOfPressure.PA,
        device_classes={SensorDeviceClass.PRESSURE},
    ),
    UnitOfMeasurement(
        unit=SIGNAL_STRENGTH_DECIBELS,
        aliases={"db"},
        device_classes={SensorDeviceClass.SIGNAL_STRENGTH},
    ),
    UnitOfMeasurement(
        unit=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        aliases={"dbm"},
        device_classes={SensorDeviceClass.SIGNAL_STRENGTH},
    ),
    UnitOfMeasurement(
        unit=UnitOfTemperature.CELSIUS,
        aliases={"°c", "c", "celsius", "℃"},
        device_classes={SensorDeviceClass.TEMPERATURE},
    ),
    UnitOfMeasurement(
        unit=UnitOfTemperature.FAHRENHEIT,
        aliases={"°f", "f", "fahrenheit"},
        device_classes={SensorDeviceClass.TEMPERATURE},
    ),
    UnitOfMeasurement(
        unit=UnitOfElectricPotential.VOLT,
        aliases={"volt"},
        device_classes={SensorDeviceClass.VOLTAGE},
    ),
    UnitOfMeasurement(
        unit=UnitOfElectricPotential.MILLIVOLT,
        aliases={"mv", "millivolt"},
        device_classes={SensorDeviceClass.VOLTAGE},
        conversion_unit=UnitOfElectricPotential.VOLT,
        conversion_fn=lambda x: x / 1000,
    ),
)


DEVICE_CLASS_UNITS: dict[str, dict[str, UnitOfMeasurement]] = {}
for uom in UNITS:
    for device_class in uom.device_classes:
        DEVICE_CLASS_UNITS.setdefault(device_class, {})[uom.unit] = uom
        for unit_alias in uom.aliases:
            DEVICE_CLASS_UNITS[device_class][unit_alias] = uom

@dataclass
class Country:
    """Describe a supported country."""

    name: str
    country_code: str
    endpoint: str = TuyaCloudOpenAPIEndpoint.AMERICA


# https://developer.tuya.com/en/docs/iot/oem-app-data-center-distributed?id=Kafi0ku9l07qb
TUYA_COUNTRIES = [
    Country("Afghanistan", "93", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Albania", "355", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Algeria", "213", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("American Samoa", "1-684", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Andorra", "376", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Angola", "244", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Anguilla", "1-264", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Antarctica", "672", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Antigua and Barbuda", "1-268", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Argentina", "54", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Armenia", "374", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Aruba", "297", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Australia", "61", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Austria", "43", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Azerbaijan", "994", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Bahamas", "1-242", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Bahrain", "973", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Bangladesh", "880", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Barbados", "1-246", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Belarus", "375", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Belgium", "32", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Belize", "501", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Benin", "229", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Bermuda", "1-441", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Bhutan", "975", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Bolivia", "591", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Bosnia and Herzegovina", "387", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Botswana", "267", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Brazil", "55", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("British Indian Ocean Territory", "246", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("British Virgin Islands", "1-284", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Brunei", "673", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Bulgaria", "359", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Burkina Faso", "226", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Burundi", "257", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Cambodia", "855", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Cameroon", "237", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Canada", "1", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Capo Verde", "238", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Cayman Islands", "1-345", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Central African Republic", "236", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Chad", "235", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Chile", "56", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("China", "86", TuyaCloudOpenAPIEndpoint.CHINA),
    Country("Christmas Island", "61"),
    Country("Cocos Islands", "61"),
    Country("Colombia", "57", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Comoros", "269", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Cook Islands", "682", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Costa Rica", "506", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Croatia", "385", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Cuba", "53"),
    Country("Curacao", "599", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Cyprus", "357", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Czech Republic", "420", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Democratic Republic of the Congo", "243", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Denmark", "45", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Djibouti", "253", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Dominica", "1-767", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Dominican Republic", "1-809", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("East Timor", "670", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Ecuador", "593", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Egypt", "20", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("El Salvador", "503", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Equatorial Guinea", "240", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Eritrea", "291", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Estonia", "372", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Ethiopia", "251", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Falkland Islands", "500", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Faroe Islands", "298", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Fiji", "679", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Finland", "358", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("France", "33", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("French Polynesia", "689", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Gabon", "241", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Gambia", "220", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Georgia", "995", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Germany", "49", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Ghana", "233", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Gibraltar", "350", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Greece", "30", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Greenland", "299", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Grenada", "1-473", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Guam", "1-671", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Guatemala", "502", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Guernsey", "44-1481"),
    Country("Guinea", "224"),
    Country("Guinea-Bissau", "245", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Guyana", "592", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Haiti", "509", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Honduras", "504", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Hong Kong", "852", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Hungary", "36", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Iceland", "354", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("India", "91", TuyaCloudOpenAPIEndpoint.INDIA),
    Country("Indonesia", "62", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Iran", "98"),
    Country("Iraq", "964", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Ireland", "353", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Isle of Man", "44-1624"),
    Country("Israel", "972", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Italy", "39", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Ivory Coast", "225", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Jamaica", "1-876", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Japan", "81", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Jersey", "44-1534"),
    Country("Jordan", "962", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Kazakhstan", "7", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Kenya", "254", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Kiribati", "686", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Kosovo", "383"),
    Country("Kuwait", "965", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Kyrgyzstan", "996", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Laos", "856", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Latvia", "371", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Lebanon", "961", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Lesotho", "266", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Liberia", "231", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Libya", "218", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Liechtenstein", "423", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Lithuania", "370", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Luxembourg", "352", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Macao", "853", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Macedonia", "389", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Madagascar", "261", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Malawi", "265", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Malaysia", "60", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Maldives", "960", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Mali", "223", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Malta", "356", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Marshall Islands", "692", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Mauritania", "222", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Mauritius", "230", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Mayotte", "262", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Mexico", "52", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Micronesia", "691", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Moldova", "373", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Monaco", "377", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Mongolia", "976", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Montenegro", "382", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Montserrat", "1-664", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Morocco", "212", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Mozambique", "258", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Myanmar", "95", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Namibia", "264", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Nauru", "674", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Nepal", "977", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Netherlands", "31", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Netherlands Antilles", "599"),
    Country("New Caledonia", "687", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("New Zealand", "64", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Nicaragua", "505", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Niger", "227", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Nigeria", "234", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Niue", "683", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("North Korea", "850"),
    Country("Northern Mariana Islands", "1-670", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Norway", "47", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Oman", "968", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Pakistan", "92", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Palau", "680", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Palestine", "970", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Panama", "507", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Papua New Guinea", "675", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Paraguay", "595", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Peru", "51", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Philippines", "63", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Pitcairn", "64"),
    Country("Poland", "48", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Portugal", "351", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Puerto Rico", "1-787, 1-939", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Qatar", "974", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Republic of the Congo", "242", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Reunion", "262", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Romania", "40", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Russia", "7", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Rwanda", "250", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Saint Barthelemy", "590", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Saint Helena", "290"),
    Country("Saint Kitts and Nevis", "1-869", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Saint Lucia", "1-758", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Saint Martin", "590", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Saint Pierre and Miquelon", "508", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country(
        "Saint Vincent and the Grenadines", "1-784", TuyaCloudOpenAPIEndpoint.EUROPE
    ),
    Country("Samoa", "685", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("San Marino", "378", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Sao Tome and Principe", "239", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Saudi Arabia", "966", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Senegal", "221", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Serbia", "381", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Seychelles", "248", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Sierra Leone", "232", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Singapore", "65", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Sint Maarten", "1-721", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Slovakia", "421", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Slovenia", "386", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Solomon Islands", "677", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Somalia", "252", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("South Africa", "27", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("South Korea", "82", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("South Sudan", "211"),
    Country("Spain", "34", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Sri Lanka", "94", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Sudan", "249"),
    Country("Suriname", "597", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Svalbard and Jan Mayen", "4779", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Swaziland", "268", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Sweden", "46", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Switzerland", "41", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Syria", "963"),
    Country("Taiwan", "886", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Tajikistan", "992", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Tanzania", "255", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Thailand", "66", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Togo", "228", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Tokelau", "690", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Tonga", "676", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Trinidad and Tobago", "1-868", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Tunisia", "216", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Turkey", "90", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Turkmenistan", "993", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Turks and Caicos Islands", "1-649", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Tuvalu", "688", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("U.S. Virgin Islands", "1-340", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Uganda", "256", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Ukraine", "380", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("United Arab Emirates", "971", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("United Kingdom", "44", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("United States", "1", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Uruguay", "598", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Uzbekistan", "998", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Vanuatu", "678", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Vatican", "379", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Venezuela", "58", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Vietnam", "84", TuyaCloudOpenAPIEndpoint.AMERICA),
    Country("Wallis and Futuna", "681", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Western Sahara", "212", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Yemen", "967", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Zambia", "260", TuyaCloudOpenAPIEndpoint.EUROPE),
    Country("Zimbabwe", "263", TuyaCloudOpenAPIEndpoint.EUROPE),
]