from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntityDescription as TuyaAlarmControlPanelEntityDescription,  # noqa: F401
)
from homeassistant.components.tuya.alarm_control_panel import (
    ALARM as ALARM_TUYA,  # noqa: F401
    TuyaAlarmEntity as TuyaAlarmEntity,
)
from homeassistant.components.tuya.binary_sensor import (
    BINARY_SENSORS as BINARY_SENSORS_TUYA,  # noqa: F401
    TuyaBinarySensorEntity as TuyaBinarySensorEntity,
    TuyaBinarySensorEntityDescription as TuyaBinarySensorEntityDescription,
)
from homeassistant.components.button import (
    ButtonEntityDescription as TuyaButtonEntityDescription,  # noqa: F401
)
from homeassistant.components.tuya.button import (
    BUTTONS as BUTTONS_TUYA,  # noqa: F401
    TuyaButtonEntity as TuyaButtonEntity,
)
from homeassistant.components.tuya.camera import (
    CAMERAS as CAMERAS_TUYA,  # noqa: F401
    TuyaCameraEntity as TuyaCameraEntity,
)
from homeassistant.components.tuya.climate import (
    CLIMATE_DESCRIPTIONS as CLIMATE_DESCRIPTIONS_TUYA,  # noqa: F401
    TuyaClimateEntity as TuyaClimateEntity,
    TuyaClimateEntityDescription as TuyaClimateEntityDescription,
    TUYA_HVAC_TO_HA as TuyaClimateHVACToHA,  # noqa: F401
)
from homeassistant.components.tuya.cover import (
    COVERS as COVERS_TUYA,  # noqa: F401
    TuyaCoverEntity as TuyaCoverEntity,
    TuyaCoverEntityDescription as TuyaCoverEntityDescription,
)
from homeassistant.components.event import (
    EventEntityDescription,
)
try:
    from homeassistant.components.tuya.event import (
        EVENTS as EVENTS_TUYA, # noqa: F401
        TuyaEventEntity as TuyaEventEntity,
    )
except Exception:
    EVENTS_TUYA: dict[str, tuple[EventEntityDescription, ...]] = {}
    from homeassistant.components.event import (
        EventEntity as TuyaEventEntity,  # noqa: F401
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
from homeassistant.components.number import (
    NumberEntityDescription as TuyaNumberEntityDescription,  # noqa: F401
)
from homeassistant.components.tuya.number import (
    NUMBERS as NUMBERS_TUYA,  # noqa: F401
    TuyaNumberEntity as TuyaNumberEntity,
)
from homeassistant.components.select import (
    SelectEntityDescription as TuyaSelectEntityDescription,  # noqa: F401
)
from homeassistant.components.tuya.select import (
    SELECTS as SELECTS_TUYA,  # noqa: F401
    TuyaSelectEntity as TuyaSelectEntity,
)
from homeassistant.components.tuya.sensor import (
    SENSORS as SENSORS_TUYA,  # noqa: F401
    TuyaSensorEntity as TuyaSensorEntity,
    TuyaSensorEntityDescription as TuyaSensorEntityDescription,
)
from homeassistant.components.siren import (
    SirenEntityDescription as TuyaSirenEntityDescription,  # noqa: F401
)
from homeassistant.components.tuya.siren import (
    SIRENS as SIRENS_TUYA,  # noqa: F401
    TuyaSirenEntity as TuyaSirenEntity,
)
from homeassistant.components.switch import (
    SwitchEntityDescription as TuyaSwitchEntityDescription,  # noqa: F401
)
from homeassistant.components.tuya.switch import (
    SWITCHES as SWITCHES_TUYA,  # noqa: F401
    TuyaSwitchEntity as TuyaSwitchEntity,
)
from homeassistant.components.tuya.vacuum import (
    TuyaVacuumEntity as TuyaVacuumEntity,
)
import homeassistant.components.tuya as tuya_integration  # noqa: F401

# from homeassistant.components.tuya import (
#    ManagerCompat as TuyaManager,
# )
from tuya_sharing.manager import (
    Manager as TuyaManager,  # noqa: F401
    CustomerDevice as TuyaCustomerDevice,  # noqa: F401
)
from homeassistant.components.tuya.const import (
    DPCode as TuyaDPCode,  # noqa: F401
    DPType as TuyaDPType,  # noqa: F401
    DOMAIN as TuyaDOMAIN,  # noqa: F401
    DEVICE_CLASS_UNITS as TuyaDEVICE_CLASS_UNITS,  # noqa: F401
)
from homeassistant.components.tuya.entity import (
    TuyaEntity as TuyaEntity,
    EnumTypeData as TuyaEnumTypeData,  # noqa: F401
    IntegerTypeData as TuyaIntegerTypeData,  # noqa: F401
    _DPTYPE_MAPPING as TUYA_DPTYPE_MAPPING,  # noqa: F401
)
from tuya_sharing.scenes import (
    SharingScene as TuyaScene,  # noqa: F401
)
from homeassistant.components.tuya.scene import (
    TuyaSceneEntity as TuyaSceneEntity,
)
