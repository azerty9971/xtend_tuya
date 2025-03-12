"""Constants for the Tuya integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum, IntFlag
import logging

from tuya_iot import TuyaCloudOpenAPIEndpoint

from homeassistant.const import (
    Platform,
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
CONF_USE_OPEN_API = "use_open_api"
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
TUYA_HA_SIGNAL_UPDATE_ENTITY = "tuya_entry_update"
TUYA_DISCOVERY_NEW = "xt_tuya_discovery_new"

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
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SCENE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
    Platform.TIME,
    Platform.VACUUM,
]

class AllowedPlugins:
    @staticmethod
    def get_plugins_to_load() -> list[str]:
        return [MESSAGE_SOURCE_TUYA_SHARING, MESSAGE_SOURCE_TUYA_IOT]

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
    vs_copy_delta_to_state: list[DPCode] = field(default_factory=list)

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
    """Data Point Codes used by XT.

    https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
    """

    ADD_ELE = "add_ele" #Added watt since last heartbeat
    ADD_ELE_THIS_MONTH = "add_ele_this_month"
    ADD_ELE_THIS_YEAR = "add_ele_this_year"
    ADD_ELE_TODAY = "add_ele_today"
    ADD_ELE2 = "add_ele2" #Added watt since last heartbeat
    ADD_ELE2_THIS_MONTH = "add_ele2_this_month"
    ADD_ELE2_THIS_YEAR = "add_ele2_this_year"
    ADD_ELE2_TODAY = "add_ele2_today"
    AIR_QUALITY = "air_quality"
    AIR_QUALITY_INDEX = "air_quality_index"
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
    A_CURRENT = "A_Current"
    A_VOLTAGE = "A_Voltage"
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
    BATTERY_POWER = "battery_power"
    BATTERY_STATE = "battery_state"  # Battery state
    BATTERY_VALUE = "battery_value"  # Battery value
    BEEP = "beep"
    BEEP_VOLUME = "beep_volume"
    BREATHDISTANCE_MAX = "breathdistance_max"
    BREATHDISTANCE_MIN = "breathdistance_min"
    BREATHSENSITIVITY = "breathsensitivity"
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
    B_CURRENT = "B_Current"
    B_VOLTAGE = "B_Voltage"
    C_F = "c_f"  # Temperature unit switching
    CALIBRATION = "calibration"
    CAPACITY_CALIBRATION = "capacity_calibration"
    CAT_WEIGHT = "cat_weight"
    CDS = "cds"
    CH2O_STATE = "ch2o_state"
    CH2O_VALUE = "ch2o_value"
    CH4_SENSOR_STATE = "ch4_sensor_state"
    CH4_SENSOR_VALUE = "ch4_sensor_value"
    CHARGE_CUR_SET = "charge_cur_set"
    CHARGE_ENERGY = "charge_energy"
    CHARGE_ENERGY_ONCE = "charge_energy_once"
    CHARGINGOPERATION = "ChargingOperation"
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
    CLEAR_ENERGY = "clear_energy"
    CLICK_SUSTAIN_TIME = "click_sustain_time"
    CLOUD_RECIPE_NUMBER = "cloud_recipe_number"
    CLOSED_OPENED = "closed_opened"
    CLOSED_OPENED_KIT = "closed_opened_kit"
    CLCT_TIME = "clct_time"
    CO_STATE = "co_state"
    CO_STATUS = "co_status"
    CO_VALUE = "co_value"
    CO2_STATE = "co2_state"
    CO2_VALUE = "co2_value"  # CO2 concentration
    COLLECTION_MODE = "collection_mode"
    COLOR = "Color"
    COLOR_DATA_V2 = "color_data_v2"
    COLOUR_DATA = "colour_data"  # Colored light mode
    COLOUR_DATA_HSV = "colour_data_hsv"  # Colored light mode
    COLOUR_DATA_V2 = "colour_data_v2"  # Colored light mode
    COOK_TEMPERATURE = "cook_temperature"
    COOK_TIME = "cook_time"
    CONCENTRATION_SET = "concentration_set"  # Concentration setting
    CONNECTION_STATE = "connection_state"
    CONTROL = "control"
    CONTROL_2 = "control_2"
    CONTROL_3 = "control_3"
    CONTROL_BACK = "control_back"
    CONTROL_BACK_MODE = "control_back_mode"
    CONTROL_SKIP = "control_skip"
    COUNTDOWN = "countdown"  # Countdown
    COUNTDOWN_1 = "countdown_1"
    COUNTDOWN_2 = "countdown_2"
    COUNTDOWN_3 = "countdown_3"
    COUNTDOWN_4 = "countdown_4"
    COUNTDOWN_5 = "countdown_5"
    COUNTDOWN_6 = "countdown_6"
    COUNTDOWN_7 = "countdown_7"
    COUNTDOWN_8 = "countdown_8"
    COUNTDOWN_LEFT = "countdown_left"
    COUNTDOWN_SET = "countdown_set"  # Countdown setting
    CRY_DETECTION_SWITCH = "cry_detection_switch"
    CTIME = "Ctime"
    CTIME2 = "CTime2"
    CUP_NUMBER = "cup_number"  # NUmber of cups
    CURRENT_YD = "current_yd"
    CUR_CURRENT = "cur_current"  # Actual current
    CUR_NEUTRAL = "cur_neutral"  # Total reverse energy
    CUR_POWER = "cur_power"  # Actual power
    CUR_VOLTAGE = "cur_voltage"  # Actual voltage
    C_CURRENT = "C_Current"
    C_VOLTAGE = "C_Voltage"
    DECIBEL_SENSITIVITY = "decibel_sensitivity"
    DECIBEL_SWITCH = "decibel_switch"
    DEHUMIDITY_SET_ENUM = "dehumidify_set_enum"
    DEHUMIDITY_SET_VALUE = "dehumidify_set_value"
    DELAY_CLEAN_TIME = "delay_clean_time"
    DEODORIZATION = "deodorization"
    DEODORIZATION_NUM = "deodorization_num"
    DEO_START_TIME = "deo_start_time"
    DEO_END_TIME = "deo_end_time"
    DETECTION_DISTANCE_MIN = "detection_distance_min"
    DETECTION_DISTANCE_MAX = "detection_distance_max"
    DETECTION_SENSITIVITY = "detection_sensitivity"
    DEVICEKW = "DeviceKw"
    DEVICEKWH = "DeviceKwh"
    DEVICEMAXSETA = "DeviceMaxSetA"
    DEVICESTATE = "DeviceState"
    DEVICETEMP = "DeviceTemp"
    DEVICETEMP2 = "DeviceTemp2"
    DEVICE_MODE = "device_mode"
    DISINFECTION = "disinfection"
    DO_NOT_DISTURB = "do_not_disturb"
    DOORBELL_VOLUME = "doorbell_volume"
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
    FAULT2 = "Fault"
    FEED_REPORT = "feed_report"
    FEED_STATE = "feed_state"
    FILTER = "filter"
    FILTER_LIFE = "filter"
    FILTER_RESET = "filter_reset"  # Filter (cartridge) reset
    FLOODLIGHT_LIGHTNESS = "floodlight_lightness"
    FLOODLIGHT_SWITCH = "floodlight_switch"
    FLOW_VELOCITY = "flow_velocity"
    FORWARD_ENERGY_TOTAL = "forward_energy_total"
    GAS_SENSOR_STATE = "gas_sensor_state"
    GAS_SENSOR_STATUS = "gas_sensor_status"
    GAS_SENSOR_VALUE = "gas_sensor_value"
    HEART_RATE = "heart_rate"
    HISTORY = "History"
    HOLD_SENSITIVITY = "hold_sensitivity"
    HUMIDIFIER = "humidifier"  # Humidification
    HUMIDITY = "humidity"  # Humidity
    HUMIDITY_CALIBRATION = "humidity_calibration"
    HUMIDITY_CURRENT = "humidity_current"  # Current humidity
    HUMIDITY_INDOOR = "humidity_indoor"  # Indoor humidity
    HUMIDITY_SET = "humidity_set"  # Humidity setting
    HUMIDITY_VALUE = "humidity_value"  # Humidity
    IDVERIFICATIONSET = "IDVerificationSet"
    ILLUMINANCE_VALUE = "illuminance_value"
    INDICATOR_LED = "indicator_led"
    INDICATOR_LIGHT = "indicator_light"
    INDUCTION_CLEAN = "Induction_Clean"
    INDUCTION_DELAY = "induction_delay"
    INDUCTION_INTERVAL = "induction_interval"
    INSTALLATION_HEIGHT = "installation_height"
    IPC_WORK_MODE = "ipc_work_mode"
    IR_CONTROL = "ir_control"
    KEY_TONE = "key_tone"
    KILL = "kill"
    LDR = "ldr"
    LED_TYPE_1 = "led_type_1"
    LED_TYPE_2 = "led_type_2"
    LED_TYPE_3 = "led_type_3"
    LEVEL = "level"
    LEVEL_CURRENT = "level_current"
    LIGHT = "light"  # Light
    LIGHT_MODE = "light_mode"
    LIQUID_DEPTH = "liquid_depth"
    LIQUID_DEPTH_MAX = "liquid_depth_max"
    LIQUID_LEVEL_PERCENT = "liquid_level_percent"
    LIQUID_STATE = "liquid_state"
    LOCK = "lock"  # Lock / Child lock
    LOCK_MOTOR_STATE = "lock_motor_state"
    MASTER_MODE = "master_mode"  # alarm mode
    MACH_OPERATE = "mach_operate"
    MAGNETNUM = "magnetNum"
    MANUAL_CLEAN = "manual_clean"
    MANUAL_FEED = "manual_feed"
    MANUAL_LOCK = "manual_lock"
    MATERIAL = "material"  # Material
    MAX_SET = "max_set"
    MINI_SET = "mini_set"
    MONITORING = "monitoring"
    MODE = "mode"  # Working mode / Mode
    MODE2 = "Mode"
    MOODLIGHTING = "moodlighting"  # Mood light
    MOTION_RECORD = "motion_record"
    MOTION_SENSITIVITY = "motion_sensitivity"
    MOTION_SWITCH = "motion_switch"  # Motion switch
    MOTION_TRACKING = "motion_tracking"
    MOVEMENT_DETECT_PIC = "movement_detect_pic"
    MOVEDISTANCE_MAX = "movedistance_max"
    MOVEDISTANCE_MIN = "movedistance_min"
    MOVESENSITIVITY = "movesensitivity"
    MUFFLING = "muffling"  # Muffling
    M_ADC_NUM = "M_ADC_NUM"
    NEAR_DETECTION = "near_detection"
    NET_NOTICE = "Net_notice"
    NONE_DELAY_TIME = "none_delay_time"
    NONE_DELAY_TIME_MIN = "none_delay_time_min"
    NONE_DELAY_TIME_SEC = "none_delay_time_sec"
    NOTIFICATION_STATUS = "notification_status"
    NOT_DISTURB = "not_disturb"
    NOT_DISTURB_SWITCH = "not_disturb_Switch"
    NUMBER = "number"
    ODOURLESS = "odourless"
    OFF = "off"
    OFF_BED = "off_bed"
    OFF_BED_TIME = "off_bed_time"
    ONLINE_STATE = "online_state"
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
    PHASEFLAG = "PhaseFlag"
    PHASE_A = "phase_a"
    PHASE_B = "phase_b"
    PHASE_C = "phase_c"
    PHOTO_AGAIN = "photo_again"
    PIR = "pir"  # Motion sensor
    PIR2 = "PIR"
    PIR_DELAY = "pir_delay"
    PIR_RADAR = "PIR_RADAR"
    PIR_SENSITIVITY = "pir_sensitivity"
    PM1 = "pm1"
    PM10 = "pm10"
    PM25 = "pm25"
    PM25_STATE = "pm25_state"
    PM25_VALUE = "pm25_value"
    POSITION = "position"
    POWDER_SET = "powder_set"  # Powder
    POWER = "power"
    POWER2 = "Power"
    POWERON = "poweron"
    POWERONOFF = "PowerOnOff"
    POWER_CONSUMPTION = "power_consumption"
    POWER_GO = "power_go"
    POWER_SET = "power_set"
    POWER_TOTAL = "power_total"
    PRESENCE_DELAY = "presence_delay"
    PRESENCE_STATE = "presence_state"
    PRESSURE_STATE = "pressure_state"
    PRESSURE_VALUE = "pressure_value"
    PUMP = "pump"
    PUMP_RESET = "pump_reset"  # Water pump reset
    QUIET_TIMING_ON = "quiet_timing_on"
    QUIET_TIME_END = "quiet_time_end"
    QUIET_TIME_START = "quiet_time_start"
    REBOOT = "reboot"
    RECIPE = "Recipe"
    RECORD_MODE = "record_mode"
    RECORD_SWITCH = "record_switch"  # Recording switch
    RELAY_STATUS = "relay_status"
    REMAININGTIME = "RemainingTime"
    REMAIN_TIME = "remain_time"
    REMOTE_NO_DP_KEY = "remote_no_dp_key"
    RESET_ADD_ELE = "reset_add_ele"
    RESET_DUSTER_CLOTH = "reset_duster_cloth"
    RESET_EDGE_BRUSH = "reset_edge_brush"
    RESET_FILTER = "reset_filter"
    RESET_MAP = "reset_map"
    RESET_ROLL_BRUSH = "reset_roll_brush"
    RESIDUAL_ELECTRICITY = "residual_electricity"
    RESPIRATORY_RATE = "respiratory_rate"
    REVERSE_ENERGY_TOTAL = "reverse_energy_total"
    RFID = "RFID"
    ROLL_BRUSH = "roll_brush"
    RTC_TIME = "rtc_time"
    SAND_SURFACE_CALIBRATION = "sand_surface_calibration"
    SEEK = "seek"
    SENSITIVITY = "sensitivity"  # Sensitivity
    SENSOR_HUMIDITY = "sensor_humidity"
    SENSOR_TEMPERATURE = "sensor_temperature"
    SETDELAYTIME = "SetDelayTime"
    SETDEFINETIME = "SetDefineTime"
    SETTIME = "SetTime"
    SET16A = "Set16A"
    SET32A = "Set32A"
    SET40A = "Set40A"
    SET50A = "Set50A"
    SHAKE = "shake"  # Oscillating
    SHOCK_STATE = "shock_state"  # Vibration status
    SIGLE_PHASE_POWER = "sigle_phase_power"
    SIREN_SWITCH = "siren_switch"
    SITUATION_SET = "situation_set"
    SLEEP = "sleep"  # Sleep function
    SLEEPING = "sleeping"
    SLEEP_END_TIME = "sleep_end_time"
    SLEEP_STAGE = "sleep_stage"
    SLEEP_START_TIME = "sleep_start_time"
    SLOW_FEED = "slow_feed"
    SMART_CLEAN = "smart_clean"
    SMOKE_SENSOR_STATE = "smoke_sensor_state"
    SMOKE_SENSOR_STATUS = "smoke_sensor_status"
    SMOKE_SENSOR_VALUE = "smoke_sensor_value"
    SOS = "sos"  # Emergency State
    SOS_STATE = "sos_state"  # Emergency mode
    SOUND = "sound"
    SOUND_MODE = "sound_mode"
    SPECIAL_FUNCTION = "special_function"
    SPEED = "speed"  # Speed level
    SPRAY_MODE = "spray_mode"  # Spraying mode
    STANDBY_BRIGHT = "standby_bright"
    STANDBY_TIME = "standby_time"
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
    SWITCH_ENABLED = "switch_enabled"
    SWITCH_FAN = "switch_fan"
    SWITCH_HORIZONTAL = "switch_horizontal"  # Horizontal swing flap switch
    SWITCH_LED = "switch_led"  # Switch
    SWITCH_LED_1 = "switch_led_1"
    SWITCH_LED_2 = "switch_led_2"
    SWITCH_LED_3 = "switch_led_3"
    SWITCH_NIGHT_LIGHT = "switch_night_light"
    SWITCH_PIR = "switch_pir"
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
    SYSTEM_VERSION = "system_version"
    TARGET_DISTANCE = "target_distance"
    TARGET_DIS_CLOSEST = "target_dis_closest"  # Closest target distance
    TEMP = "temp"  # Temperature setting
    TEMPCHANGER = "TempChanger"
    TEMPERATURE = "temperature"
    TEMPER_ALARM = "temper_alarm"  # Tamper alarm
    TEMPSC = "TempSc"
    TEMPSET = "TempSet"
    TEMPSHOW = "TempShow"
    TEMP_ADC = "temp_adc"
    TEMP_BOILING_C = "temp_boiling_c"
    TEMP_BOILING_F = "temp_boiling_f"
    TEMP_BOTTOM = "temp_bottom"
    TEMP_CALIBRATION = "temp_calibration"
    TEMP_CONTROLLER = "temp_controller"
    TEMP_CURRENT = "temp_current"  # Current temperature in °C
    TEMP_CURRENT_F = "temp_current_f"  # Current temperature in °F
    TEMP_INDOOR = "temp_indoor"  # Indoor temperature in °C
    TEMP_SET = "temp_set"  # Set the temperature in °C
    TEMP_SET_1 = "temp_set_1"  # Set the warm temperature in °C
    TEMP_SET_F = "temp_set_f"  # Set the temperature in °F
    TEMP_UNIT_CONVERT = "temp_unit_convert"  # Temperature unit switching
    TEMP_VALUE = "temp_value"  # Color temperature
    TEMP_VALUE_V2 = "temp_value_v2"
    TEMP_TOP = "temp_top"
    TIME_TOTAL = "time_total"
    TOILET_NOTICE = "toilet_notice"
    TIME_GET_IN_BED = "time_get_in_bed"
    TIME_USE = "time_use"  # Total seconds of irrigation
    TIMER_ON = "timer_on"
    TOTAL_CLEAN_AREA = "total_clean_area"
    TOTAL_CLEAN_COUNT = "total_clean_count"
    TOTAL_CLEAN_TIME = "total_clean_time"
    TOTAL_FORWARD_ENERGY = "total_forward_energy"
    TOTAL_TIME = "total_time"
    TOTAL_PM = "total_pm"
    TOTAL_POWER = "total_power"
    TRASH_STATUS = "trash_status"
    TRIGGER_SENSITIVITY = "trigger_sensitivity"
    TVOC = "tvoc"
    UNIT = "unit"
    UPPER_TEMP = "upper_temp"
    UPPER_TEMP_F = "upper_temp_f"
    USAGE_TIMES = "usage_times"
    USE_TIME_1 = "use_time_1"
    USE_TIME_2 = "use_time_2"
    USE_TIME_3 = "use_time_3"
    USE_TIME_4 = "use_time_4"
    USE_TIME_5 = "use_time_5"
    USE_TIME_6 = "use_time_6"
    USE_TIME_7 = "use_time_7"
    USE_TIME_8 = "use_time_8"
    UV = "uv"  # UV sterilization
    UV_START_TIME = "uv_start_time"
    UV_END_TIME = "uv_end_time"
    UV_LIGHT = "uv_light"
    VA_BATTERY = "va_battery"
    VA_HUMIDITY = "va_humidity"
    VA_TEMPERATURE = "va_temperature"
    VOC_STATE = "voc_state"
    VOC_VALUE = "voc_value"
    VOICE_SWITCH = "voice_switch"
    VOICE_TIMES = "voice_times"
    VOLUME_SET = "volume_set"
    VOL_YD = "vol_yd"
    VOLTAGE_CURRENT = "voltage_current"
    WAKEUP = "wakeup"
    WARM = "warm"  # Heat preservation
    WARM_TIME = "warm_time"  # Heat preservation time
    WATER = "water"
    WATER_CONTROL = "water_control"
    WATER_ONCE = "water_once"
    WATER_RESET = "water_reset"  # Resetting of water usage days
    WATER_SET = "water_set"  # Water level
    WATER_TOTAL = "water_total"
    WATER_USE_DATA = "water_use_data"
    WATERSENSOR_STATE = "watersensor_state"
    WEATHER_DELAY = "weather_delay"
    WEATHER_SWITCH = "weather_switch"
    WET = "wet"  # Humidification
    WINDOW_CHECK = "window_check"
    WINDOW_STATE = "window_state"
    WINDSPEED = "windspeed"
    WIRELESS_BATTERYLOCK = "wireless_batterylock"
    WIRELESS_ELECTRICITY = "wireless_electricity"
    WORK_MODE = "work_mode"  # Working mode
    WORK_POWER = "work_power"
    WORK_STAT = "work_stat"
    WORK_STATE = "work_state"
    WORK_STATUS = "WorkStatus"

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
