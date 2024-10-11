from ...const import (
    LOGGER,  # noqa: F401
)
try:
    from custom_components.tuya.alarm_control_panel import ( # type: ignore
        ALARM as ALARM_TUYA
    )
except ImportError:
    from homeassistant.components.tuya.alarm_control_panel import (
        ALARM as ALARM_TUYA  # noqa: F401
    )
try:
    from custom_components.tuya.binary_sensor import ( # type: ignore
        BINARY_SENSORS as BINARY_SENSORS_TUYA
    )
except ImportError:
    from homeassistant.components.tuya.binary_sensor import (
        BINARY_SENSORS as BINARY_SENSORS_TUYA  # noqa: F401
    )
try:
    from custom_components.tuya.button import ( # type: ignore
        BUTTONS as BUTTONS_TUYA
    )
except ImportError:
    from homeassistant.components.tuya.button import (
        BUTTONS as BUTTONS_TUYA  # noqa: F401
    )
try:
    from custom_components.tuya.camera import ( # type: ignore
        CAMERAS as CAMERAS_TUYA  # noqa: F401
    )
except ImportError:
    from homeassistant.components.tuya.camera import (
        CAMERAS as CAMERAS_TUYA  # noqa: F401
    )
try:
    from custom_components.tuya.climate import ( # type: ignore
        CLIMATE_DESCRIPTIONS as CLIMATE_DESCRIPTIONS_TUYA
    )
except ImportError:
    from homeassistant.components.tuya.climate import (
        CLIMATE_DESCRIPTIONS as CLIMATE_DESCRIPTIONS_TUYA  # noqa: F401
    )
try:
    from custom_components.tuya.cover import ( # type: ignore
        COVERS as COVERS_TUYA
    )
except ImportError:
    from homeassistant.components.tuya.cover import (
        COVERS as COVERS_TUYA  # noqa: F401
    )
try:
    from custom_components.tuya.fan import ( # type: ignore
        TUYA_SUPPORT_TYPE as FANS_TUYA
    )
except ImportError:
    from homeassistant.components.tuya.fan import (
        TUYA_SUPPORT_TYPE as FANS_TUYA  # noqa: F401
    )
try:
    from custom_components.tuya.humidifier import ( # type: ignore
        HUMIDIFIERS as HUMIDIFIERS_TUYA
    )
except ImportError:
    from homeassistant.components.tuya.humidifier import (
        HUMIDIFIERS as HUMIDIFIERS_TUYA  # noqa: F401
    )
try:
    from custom_components.tuya.light import ( # type: ignore
        LIGHTS as LIGHTS_TUYA
    )
except ImportError:
    from homeassistant.components.tuya.light import (
        LIGHTS as LIGHTS_TUYA  # noqa: F401
    )
try:
    from custom_components.tuya.number import ( # type: ignore
        NUMBERS as NUMBERS_TUYA
    )
except ImportError:
    from homeassistant.components.tuya.number import (
        NUMBERS as NUMBERS_TUYA  # noqa: F401
    )
try:
    from custom_components.tuya.select import ( # type: ignore
        SELECTS as SELECTS_TUYA
    )
except ImportError:
    from homeassistant.components.tuya.select import (
        SELECTS as SELECTS_TUYA  # noqa: F401
    )
try:
    from custom_components.tuya.sensor import ( # type: ignore
        SENSORS as SENSORS_TUYA
    )
except ImportError:
    from homeassistant.components.tuya.sensor import (
        SENSORS as SENSORS_TUYA  # noqa: F401
    )
try:
    from custom_components.tuya.siren import ( # type: ignore
        SIRENS as SIRENS_TUYA
    )
except ImportError:
    from homeassistant.components.tuya.siren import (
        SIRENS as SIRENS_TUYA  # noqa: F401
    )
try:
    from custom_components.tuya.switch import ( # type: ignore
        SWITCHES as SWITCHES_TUYA
    )
except ImportError:
    from homeassistant.components.tuya.switch import (
        SWITCHES as SWITCHES_TUYA  # noqa: F401
    )
try:
    import custom_components.tuya as tuya_integration # type: ignore
except ImportError:
    import homeassistant.components.tuya as tuya_integration  # noqa: F401
