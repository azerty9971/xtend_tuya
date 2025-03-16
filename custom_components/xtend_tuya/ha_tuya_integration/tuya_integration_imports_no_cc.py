from homeassistant.components.tuya.alarm_control_panel import (
        ALARM as ALARM_TUYA,  # noqa: F401
        TuyaAlarmEntity as TuyaAlarmEntity,
        AlarmControlPanelEntityDescription as TuyaAlarmControlPanelEntityDescription,
    )
from homeassistant.components.tuya.binary_sensor import (
        BINARY_SENSORS as BINARY_SENSORS_TUYA,  # noqa: F401
        TuyaBinarySensorEntity as TuyaBinarySensorEntity,
        TuyaBinarySensorEntityDescription as TuyaBinarySensorEntityDescription,
    )
from homeassistant.components.tuya.button import (
        BUTTONS as BUTTONS_TUYA,  # noqa: F401
        TuyaButtonEntity as TuyaButtonEntity,
        ButtonEntityDescription as TuyaButtonEntityDescription,
    )
from homeassistant.components.tuya.camera import (
        CAMERAS as CAMERAS_TUYA,  # noqa: F401
        TuyaCameraEntity as TuyaCameraEntity,
    )
from homeassistant.components.tuya.climate import (
        CLIMATE_DESCRIPTIONS as CLIMATE_DESCRIPTIONS_TUYA,  # noqa: F401
        TuyaClimateEntity as TuyaClimateEntity,
        TuyaClimateEntityDescription as TuyaClimateEntityDescription,
        TUYA_HVAC_TO_HA as TuyaClimateHVACToHA,
    )
from homeassistant.components.tuya.cover import (
        COVERS as COVERS_TUYA,  # noqa: F401
        TuyaCoverEntity as TuyaCoverEntity,
        TuyaCoverEntityDescription as TuyaCoverEntityDescription,
    )
from homeassistant.components.tuya.fan import (
        TUYA_SUPPORT_TYPE as FANS_TUYA,  # noqa: F401
        TuyaFanEntity as TuyaFanEntity,
    )
from homeassistant.components.tuya.humidifier import (
        HUMIDIFIERS as HUMIDIFIERS_TUYA,  # noqa: F401
        TuyaHumidifierEntity as TuyaHumidifierEntity,
        TuyaHumidifierEntityDescription as TuyaHumidifierEntityDescription,
    )
from homeassistant.components.tuya.light import (
        LIGHTS as LIGHTS_TUYA,  # noqa: F401
        TuyaLightEntity as TuyaLightEntity,
        TuyaLightEntityDescription as TuyaLightEntityDescription,
    )
from homeassistant.components.tuya.number import (
        NUMBERS as NUMBERS_TUYA,  # noqa: F401
        TuyaNumberEntity as TuyaNumberEntity,
        NumberEntityDescription as TuyaNumberEntityDescription,
    )
from homeassistant.components.tuya.select import (
        SELECTS as SELECTS_TUYA,  # noqa: F401
        TuyaSelectEntity as TuyaSelectEntity,
        SelectEntityDescription as TuyaSelectEntityDescription,
    )
from homeassistant.components.tuya.sensor import (
        SENSORS as SENSORS_TUYA,  # noqa: F401
        TuyaSensorEntity as TuyaSensorEntity,
        TuyaSensorEntityDescription as TuyaSensorEntityDescription,
    )
from homeassistant.components.tuya.siren import (
        SIRENS as SIRENS_TUYA,  # noqa: F401
        TuyaSirenEntity as TuyaSirenEntity,
        SirenEntityDescription as TuyaSirenEntityDescription,
    )
from homeassistant.components.tuya.switch import (
        SWITCHES as SWITCHES_TUYA,  # noqa: F401
        TuyaSwitchEntity as TuyaSwitchEntity,
        SwitchEntityDescription as TuyaSwitchEntityDescription,
    )
from homeassistant.components.tuya.vacuum import (
        TuyaVacuumEntity as TuyaVacuumEntity,
    )
import homeassistant.components.tuya as tuya_integration  # noqa: F401
from homeassistant.components.tuya.const import (
        DPCode as TuyaDPCode,
        DPType as TuyaDPType,
        DOMAIN as TuyaDOMAIN,
        DEVICE_CLASS_UNITS as TuyaDEVICE_CLASS_UNITS,
    )
from homeassistant.components.tuya.entity import (
        TuyaEntity as TuyaEntity,
        ElectricityTypeData as TuyaElectricityTypeData,
        EnumTypeData as TuyaEnumTypeData,
        IntegerTypeData as TuyaIntegerTypeData,
        _DPTYPE_MAPPING as TUYA_DPTYPE_MAPPING,
    )
from homeassistant.components.tuya.scene import (
        TuyaSceneEntity as TuyaSceneEntity,
        SharingScene as TuyaScene,
    )