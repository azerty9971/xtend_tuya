from .tuya_integration_imports_no_cc import *
""" try:
    from custom_components.tuya.alarm_control_panel import ( # type: ignore
        ALARM as ALARM_TUYA,
        TuyaAlarmEntity as TuyaAlarmEntity,
        AlarmControlPanelEntityDescription as TuyaAlarmControlPanelEntityDescription,
    )
except ImportError:
    from homeassistant.components.tuya.alarm_control_panel import (
        ALARM as ALARM_TUYA,  # noqa: F401
        TuyaAlarmEntity as TuyaAlarmEntity,
        AlarmControlPanelEntityDescription as TuyaAlarmControlPanelEntityDescription,
    )
try:
    from custom_components.tuya.binary_sensor import ( # type: ignore
        BINARY_SENSORS as BINARY_SENSORS_TUYA,
        TuyaBinarySensorEntity as TuyaBinarySensorEntity,
        TuyaBinarySensorEntityDescription as TuyaBinarySensorEntityDescription,
    )
except ImportError:
    from homeassistant.components.tuya.binary_sensor import (
        BINARY_SENSORS as BINARY_SENSORS_TUYA,  # noqa: F401
        TuyaBinarySensorEntity as TuyaBinarySensorEntity,
        TuyaBinarySensorEntityDescription as TuyaBinarySensorEntityDescription,
    )
try:
    from custom_components.tuya.button import ( # type: ignore
        BUTTONS as BUTTONS_TUYA,
        TuyaButtonEntity as TuyaButtonEntity,
        ButtonEntityDescription as TuyaButtonEntityDescription,
    )
except ImportError:
    from homeassistant.components.tuya.button import (
        BUTTONS as BUTTONS_TUYA,  # noqa: F401
        TuyaButtonEntity as TuyaButtonEntity,
        ButtonEntityDescription as TuyaButtonEntityDescription,
    )
try:
    from custom_components.tuya.camera import ( # type: ignore
        CAMERAS as CAMERAS_TUYA,  # noqa: F401
        TuyaCameraEntity as TuyaCameraEntity,
    )
except ImportError:
    from homeassistant.components.tuya.camera import (
        CAMERAS as CAMERAS_TUYA,  # noqa: F401
        TuyaCameraEntity as TuyaCameraEntity,
    )
try:
    from custom_components.tuya.climate import ( # type: ignore
        CLIMATE_DESCRIPTIONS as CLIMATE_DESCRIPTIONS_TUYA,
        TuyaClimateEntity as TuyaClimateEntity,
        TuyaClimateEntityDescription as TuyaClimateEntityDescription,
        TUYA_HVAC_TO_HA as TuyaClimateHVACToHA,
    )
except ImportError:
    from homeassistant.components.tuya.climate import (
        CLIMATE_DESCRIPTIONS as CLIMATE_DESCRIPTIONS_TUYA,  # noqa: F401
        TuyaClimateEntity as TuyaClimateEntity,
        TuyaClimateEntityDescription as TuyaClimateEntityDescription,
        TUYA_HVAC_TO_HA as TuyaClimateHVACToHA,
    )
try:
    from custom_components.tuya.cover import ( # type: ignore
        COVERS as COVERS_TUYA,
        TuyaCoverEntity as TuyaCoverEntity,
        TuyaCoverEntityDescription as TuyaCoverEntityDescription,
    )
except ImportError:
    from homeassistant.components.tuya.cover import (
        COVERS as COVERS_TUYA,  # noqa: F401
        TuyaCoverEntity as TuyaCoverEntity,
        TuyaCoverEntityDescription as TuyaCoverEntityDescription,
    )
try:
    from custom_components.tuya.fan import ( # type: ignore
        TUYA_SUPPORT_TYPE as FANS_TUYA,
        TuyaFanEntity as TuyaFanEntity,
    )
except ImportError:
    from homeassistant.components.tuya.fan import (
        TUYA_SUPPORT_TYPE as FANS_TUYA,  # noqa: F401
        TuyaFanEntity as TuyaFanEntity,
    )
try:
    from custom_components.tuya.humidifier import ( # type: ignore
        HUMIDIFIERS as HUMIDIFIERS_TUYA,
        TuyaHumidifierEntity as TuyaHumidifierEntity,
        TuyaHumidifierEntityDescription as TuyaHumidifierEntityDescription,
    )
except ImportError:
    from homeassistant.components.tuya.humidifier import (
        HUMIDIFIERS as HUMIDIFIERS_TUYA,  # noqa: F401
        TuyaHumidifierEntity as TuyaHumidifierEntity,
        TuyaHumidifierEntityDescription as TuyaHumidifierEntityDescription,
    )
try:
    from custom_components.tuya.light import ( # type: ignore
        LIGHTS as LIGHTS_TUYA,
        TuyaLightEntity as TuyaLightEntity,
        TuyaLightEntityDescription as TuyaLightEntityDescription,
    )
except ImportError:
    from homeassistant.components.tuya.light import (
        LIGHTS as LIGHTS_TUYA,  # noqa: F401
        TuyaLightEntity as TuyaLightEntity,
        TuyaLightEntityDescription as TuyaLightEntityDescription,
    )
try:
    from custom_components.tuya.number import ( # type: ignore
        NUMBERS as NUMBERS_TUYA,
        TuyaNumberEntity as TuyaNumberEntity,
        NumberEntityDescription as TuyaNumberEntityDescription,
    )
except ImportError:
    from homeassistant.components.tuya.number import (
        NUMBERS as NUMBERS_TUYA,  # noqa: F401
        TuyaNumberEntity as TuyaNumberEntity,
        NumberEntityDescription as TuyaNumberEntityDescription,
    )
try:
    from custom_components.tuya.select import ( # type: ignore
        SELECTS as SELECTS_TUYA,
        TuyaSelectEntity as TuyaSelectEntity,
        SelectEntityDescription as TuyaSelectEntityDescription,
    )
except ImportError:
    from homeassistant.components.tuya.select import (
        SELECTS as SELECTS_TUYA,  # noqa: F401
        TuyaSelectEntity as TuyaSelectEntity,
        SelectEntityDescription as TuyaSelectEntityDescription,
    )
try:
    from custom_components.tuya.sensor import ( # type: ignore
        SENSORS as SENSORS_TUYA,
        TuyaSensorEntity as TuyaSensorEntity,
        TuyaSensorEntityDescription as TuyaSensorEntityDescription,
    )
except ImportError:
    from homeassistant.components.tuya.sensor import (
        SENSORS as SENSORS_TUYA,  # noqa: F401
        TuyaSensorEntity as TuyaSensorEntity,
        TuyaSensorEntityDescription as TuyaSensorEntityDescription,
    )
try:
    from custom_components.tuya.siren import ( # type: ignore
        SIRENS as SIRENS_TUYA,
        TuyaSirenEntity as TuyaSirenEntity,
        SirenEntityDescription as TuyaSirenEntityDescription,
    )
except ImportError:
    from homeassistant.components.tuya.siren import (
        SIRENS as SIRENS_TUYA,  # noqa: F401
        TuyaSirenEntity as TuyaSirenEntity,
        SirenEntityDescription as TuyaSirenEntityDescription,
    )
try:
    from custom_components.tuya.switch import ( # type: ignore
        SWITCHES as SWITCHES_TUYA,
        TuyaSwitchEntity as TuyaSwitchEntity,
        SwitchEntityDescription as TuyaSwitchEntityDescription,
    )
except ImportError:
    from homeassistant.components.tuya.switch import (
        SWITCHES as SWITCHES_TUYA,  # noqa: F401
        TuyaSwitchEntity as TuyaSwitchEntity,
        SwitchEntityDescription as TuyaSwitchEntityDescription,
    )
try:
    from custom_components.tuya.vacuum import ( # type: ignore
        TuyaVacuumEntity as TuyaVacuumEntity,
    )
except ImportError:
    from homeassistant.components.tuya.vacuum import (
        TuyaVacuumEntity as TuyaVacuumEntity,
    )
try:
    import custom_components.tuya as tuya_integration # type: ignore
except ImportError:
    import homeassistant.components.tuya as tuya_integration  # noqa: F401
try:
    from custom_components.tuya.const import (
        DPCode as TuyaDPCode,
        DPType as TuyaDPType,
    )
except ImportError:
    from homeassistant.components.tuya.const import (
        DPCode as TuyaDPCode,
        DPType as TuyaDPType,
    )
try:
    from custom_components.tuya.entity import ( # type: ignore
        TuyaEntity as TuyaEntity,
        ElectricityTypeData as TuyaElectricityTypeData,
        EnumTypeData as TuyaEnumTypeData,
        IntegerTypeData as TuyaIntegerTypeData,
        _DPTYPE_MAPPING as TUYA_DPTYPE_MAPPING,
    )
except ImportError:
    from homeassistant.components.tuya.entity import (
        TuyaEntity as TuyaEntity,   # noqa: F401
        ElectricityTypeData as TuyaElectricityTypeData,
        EnumTypeData as TuyaEnumTypeData,
        IntegerTypeData as TuyaIntegerTypeData,
        _DPTYPE_MAPPING as TUYA_DPTYPE_MAPPING,
    )
try:
    from custom_components.tuya.scene import (
        TuyaSceneEntity as TuyaSceneEntity,
        SharingScene as TuyaScene,
    )
except ImportError:
    from homeassistant.components.tuya.scene import (
        TuyaSceneEntity as TuyaSceneEntity,
        SharingScene as TuyaScene,
    )
 """