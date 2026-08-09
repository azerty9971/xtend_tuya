"""Support for XT Climate."""

from __future__ import annotations
import collections
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, cast, Self
from tuya_device_handlers.definition.climate import (
    ClimateDefinition,
    _get_temperature_wrapper,
)
from tuya_device_handlers.device_wrapper.common import (
    DPCodeBooleanWrapper,
    DPCodeEnumWrapper,
    DPCodeIntegerWrapper,
)
from tuya_device_handlers.device_wrapper.extended import (
    DPCodeRoundedIntegerWrapper,
)
from tuya_device_handlers.helpers.homeassistant import (
    TuyaClimateHVACMode,
    TuyaUnitOfTemperature,
)
from tuya_device_handlers.device_wrapper.climate import (
    DefaultHVACModeWrapper,
    DefaultPresetModeWrapper,
    SwingModeCompositeWrapper,
    _DEFAULT_DEVICE_MODE_TO_HVACMODE as TuyaClimateHVACToHA,
)
from homeassistant.components.climate.const import (
    HVACMode,
    HVACAction,
    SWING_OFF,
    SWING_ON,
    SWING_HORIZONTAL,
    SWING_VERTICAL,
)
from homeassistant.const import Platform, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .util import (
    append_dictionnaries,
    append_tuples,
)
from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .const import (
    TUYA_DISCOVERY_NEW,
    XTDPCode,
    XT_CELSIUS_ALIASES,
    XT_FAHRENHEIT_ALIASES,
    LOGGER,  # noqa: F401
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaClimateEntity,
    TuyaClimateEntityDescription,
    TuyaDPCodeEnumWrapper,
    TuyaDPCodeBooleanWrapper,
    TuyaCustomerDevice,
    TuyaEnumTypeInformation,
    TUYA_TUYA_TO_HA_HVACMODE_MAPPINGS,
    TUYA_HA_TO_TUYA_TEMPERATURE,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)

XT_HVAC_TUYA_TO_TUYALIB = {
    "auto": TuyaClimateHVACMode.AUTO,
    "cold": TuyaClimateHVACMode.COOL,
    "cool": TuyaClimateHVACMode.COOL,
    "Cool": TuyaClimateHVACMode.COOL,
    "dehumidify": TuyaClimateHVACMode.DRY,
    "Eco": TuyaClimateHVACMode.HEAT_COOL,
    "Fan": TuyaClimateHVACMode.FAN_ONLY,
    "freeze": TuyaClimateHVACMode.COOL,
    "heat": TuyaClimateHVACMode.HEAT,
    "Heat": TuyaClimateHVACMode.HEAT,
    "home": TuyaClimateHVACMode.HEAT_COOL,
    "hot": TuyaClimateHVACMode.HEAT,
    "manual": TuyaClimateHVACMode.HEAT_COOL,
    "smartcool": TuyaClimateHVACMode.HEAT_COOL,
    "temporary": TuyaClimateHVACMode.HEAT_COOL,
    "wet": TuyaClimateHVACMode.DRY,
    "wind": TuyaClimateHVACMode.FAN_ONLY,
}

MERGED_HVAC_TUYA_TO_TUYALIB: dict[str, TuyaClimateHVACMode] = append_dictionnaries(
    XT_HVAC_TUYA_TO_TUYALIB, TuyaClimateHVACToHA
)

XT_TUYALIB_TO_HA_HVACMODE_MAPPINGS = {}
MERGED_TUYALIB_TO_HA_HVACMODE_MAPPINGS: dict[TuyaClimateHVACMode, HVACMode] = (
    append_dictionnaries(
        XT_TUYALIB_TO_HA_HVACMODE_MAPPINGS, TUYA_TUYA_TO_HA_HVACMODE_MAPPINGS
    )
)

XT_HVAC_ACTION_TO_HA = {
    "heating": HVACAction.HEATING,
    "stop": HVACAction.IDLE,
}

XT_CLIMATE_MODE_DPCODES: tuple[XTDPCode, ...] = (
    XTDPCode.MODE,
    XTDPCode.MODE1,
)
XT_CLIMATE_CURRENT_NON_UNIT_TEMPERATURE_DPCODES: tuple[XTDPCode, ...] = (
    XTDPCode.GET_TEMP,
)
XT_CLIMATE_CURRENT_CELSIUS_TEMPERATURE_DPCODES: tuple[XTDPCode, ...] = (
    XTDPCode.TEMP_CURRENT,
    XTDPCode.TEMP_CURRENT_CAP,
    XTDPCode.UPPER_TEMP,
)
XT_CLIMATE_CURRENT_FAHRENHEIT_TEMPERATURE_DPCODES: tuple[XTDPCode, ...] = (
    XTDPCode.TEMP_CURRENT_F,
    XTDPCode.TEMP_CURRENT_F_CAP,
    XTDPCode.UPPER_TEMP_F,
)
XT_CLIMATE_CURRENT_TEMPERATURE_DPCODES: tuple[XTDPCode, ...] = append_tuples(
    append_tuples(
        XT_CLIMATE_CURRENT_CELSIUS_TEMPERATURE_DPCODES,
        XT_CLIMATE_CURRENT_FAHRENHEIT_TEMPERATURE_DPCODES,
    ),
    XT_CLIMATE_CURRENT_NON_UNIT_TEMPERATURE_DPCODES,
)
XT_CLIMATE_SET_CELSIUS_TEMPERATURE_DPCODES: tuple[XTDPCode, ...] = (
    XTDPCode.TEMP_SET,
    XTDPCode.TEMP_SET_CAP,
    XTDPCode.TEMPSET,
)
XT_CLIMATE_SET_FAHRENHEIT_TEMPERATURE_DPCODES: tuple[XTDPCode, ...] = (
    XTDPCode.TEMP_SET_F,
    XTDPCode.TEMP_SET_F_CAP,
)
XT_CLIMATE_SET_TEMPERATURE_DPCODES: tuple[XTDPCode, ...] = append_tuples(
    XT_CLIMATE_SET_CELSIUS_TEMPERATURE_DPCODES,
    XT_CLIMATE_SET_FAHRENHEIT_TEMPERATURE_DPCODES,
)
XT_CLIMATE_TEMPERATURE_UNIT_DPCODES: tuple[XTDPCode, ...] = (
    XTDPCode.C_F,
    XTDPCode.C_F_,
    XTDPCode.TEMP_UNIT_CONVERT,
)
XT_CLIMATE_CURRENT_HUMIDITY_DPCODES: tuple[XTDPCode, ...] = (
    XTDPCode.HUMIDITY_CURRENT,
    XTDPCode.GET_HUM,
)
XT_CLIMATE_SET_HUMIDITY_DPCODES: tuple[XTDPCode, ...] = (
    XTDPCode.HUMIDITY_SET,
    XTDPCode.HUMIDITY,
)
XT_CLIMATE_FAN_SPEED_DPCODES: tuple[XTDPCode, ...] = (
    XTDPCode.FAN_SPEED_ENUM,
    XTDPCode.LEVEL,
    XTDPCode.WINDSPEED,
    XTDPCode.WINDSPEED1,
)
XT_CLIMATE_SWING_MODE_ON_DPCODES: tuple[XTDPCode, ...] = (
    XTDPCode.SHAKE,
    XTDPCode.SWING,
    XTDPCode.WINDSHAKE,
    XTDPCode.WINDSHAKE1,
)
XT_CLIMATE_SWING_MODE_ENUM_VALUE_MAPPING: dict[str, bool] = {
    "off": False,
    "on": True,
}
XT_CLIMATE_SWING_MODE_HORIZONTAL_DPCODES: tuple[XTDPCode, ...] = (
    XTDPCode.SWITCH_HORIZONTAL,
    XTDPCode.WINDSHAKEH,
)
XT_CLIMATE_SWING_MODE_VERTICAL_DPCODES: tuple[XTDPCode, ...] = (
    XTDPCode.SWITCH_VERTICAL,
)
XT_CLIMATE_SWING_MODE_DPCODES: tuple[XTDPCode, ...] = append_tuples(
    append_tuples(
        XT_CLIMATE_SWING_MODE_ON_DPCODES, XT_CLIMATE_SWING_MODE_HORIZONTAL_DPCODES
    ),
    XT_CLIMATE_SWING_MODE_VERTICAL_DPCODES,
)
XT_CLIMATE_SWITCH_DPCODES: tuple[XTDPCode, ...] = (
    XTDPCode.SWITCH,
    XTDPCode.SWITCH_CAP,
    XTDPCode.POWER,
    XTDPCode.POWER2,
)

XT_CLIMATE_HVAC_ACTION_DPCODES: tuple[XTDPCode, ...] = (XTDPCode.WORK_STATE,)


@dataclass
class XTClimateDefinition(ClimateDefinition):
    hvac_mode_wrapper: XTClimateHvacModeWrapper | None  # type: ignore
    hvac_action_wrapper: TuyaDPCodeEnumWrapper | None


@dataclass
class XTClimateConfigurableProperties:
    current_temperature_value_multiplicator: float | None = None
    current_humidity_value_multiplicator: float | None = None
    target_temperature_value_multiplicator: float | None = None
    target_humidity_value_multiplicator: float | None = None


@dataclass(frozen=True, kw_only=True)
class XTClimateEntityDescription(TuyaClimateEntityDescription):
    """Describe an Tuya climate entity."""

    switch_only_hvac_mode: HVACMode

    # duplicate the entity if handled by another integration
    ignore_other_dp_code_handler: bool = False

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTClimateEntityDescription,
        definition: XTClimateDefinition,
    ) -> XTClimateEntity:
        return XTClimateEntity(
            device=device,
            device_manager=device_manager,
            description=XTClimateEntityDescription(**description.__dict__),
            definition=definition,
        )


CLIMATE_DESCRIPTIONS: dict[str, XTClimateEntityDescription] = {
    "cs": XTClimateEntityDescription(
        key="cs",
        switch_only_hvac_mode=HVACMode.DRY,
    ),
    "rs": XTClimateEntityDescription(
        key="rs",
        switch_only_hvac_mode=HVACMode.AUTO,
    ),
    "xfjDISABLED": XTClimateEntityDescription(
        key="xfj",
        switch_only_hvac_mode=HVACMode.AUTO,
    ),
    "ydkt": XTClimateEntityDescription(
        key="ydkt",
        switch_only_hvac_mode=HVACMode.COOL,
    ),
}


def _filter_hvac_mode_mappings(
    tuya_range: list[str],
) -> dict[str, TuyaClimateHVACMode | None]:
    """Filter TUYA_HVAC_TO_HA modes that are not in the range.

    If multiple Tuya modes map to the same HA mode, set the mapping to None to avoid
    ambiguity when converting back from HA to Tuya modes.
    """
    modes_in_range = {
        tuya_mode: MERGED_HVAC_TUYA_TO_TUYALIB.get(tuya_mode)
        for tuya_mode in tuya_range
    }
    modes_occurrences = collections.Counter(modes_in_range.values())
    for key, value in modes_in_range.items():
        if value is not None and modes_occurrences[value] > 1:
            modes_in_range[key] = None
    return modes_in_range


class XTClimatePresetWrapper(DefaultPresetModeWrapper):
    def __init__(self, dpcode: str, type_information: TuyaEnumTypeInformation) -> None:
        """Init _PresetWrapper."""
        super().__init__(dpcode, type_information)
        mappings = _filter_hvac_mode_mappings(type_information.range)
        self.options = [
            tuya_mode for tuya_mode, ha_mode in mappings.items() if ha_mode is None
        ]

    def read_device_status(self, device: TuyaCustomerDevice) -> str | None:
        """Read the device status."""
        if (
            raw := super(TuyaDPCodeEnumWrapper, self).read_device_status(device)
        ) in self.options:
            return raw
        return None


class XTClimateHvacModeWrapper(DefaultHVACModeWrapper):
    def __init__(self, dpcode: str, type_information: TuyaEnumTypeInformation) -> None:
        """Init _HvacModeWrapper."""
        super().__init__(dpcode, type_information)
        self._mappings = _filter_hvac_mode_mappings(type_information.range)
        self.options = [
            ha_mode for ha_mode in self._mappings.values() if ha_mode is not None
        ]
        self.replace_heat_cool_with: TuyaClimateHVACMode | None = None

    def read_device_status(
        self, device: TuyaCustomerDevice
    ) -> TuyaClimateHVACMode | None:
        """Read the device status."""
        if (
            raw := super(TuyaDPCodeEnumWrapper, self).read_device_status(device)
        ) not in MERGED_HVAC_TUYA_TO_TUYALIB:
            return None
        base_value = MERGED_HVAC_TUYA_TO_TUYALIB[raw]
        if base_value == HVACMode.HEAT_COOL and self.replace_heat_cool_with is not None:
            return self.replace_heat_cool_with
        return base_value

    def remap_heat_cool_based_on_action_wrapper(
        self, action_wrapper: TuyaDPCodeEnumWrapper | None
    ):
        if action_wrapper is None:
            return
        has_heating = False
        has_cooling = False
        for option in action_wrapper.options:
            if option in XT_HVAC_ACTION_TO_HA:
                match XT_HVAC_ACTION_TO_HA[option]:
                    case HVACAction.HEATING:
                        has_heating = True
                    case HVACAction.COOLING:
                        has_cooling = True

        if has_heating and has_cooling:
            # Device has both cooling and heating, don't change anything
            return
        if has_heating:
            self.replace_heat_cool_with = TuyaClimateHVACMode.HEAT

        if has_cooling:
            self.replace_heat_cool_with = TuyaClimateHVACMode.COOL


class XTClimateSwingModeWrapper(SwingModeCompositeWrapper):
    @classmethod
    def find_dpcode(cls, device: TuyaCustomerDevice) -> Self | None:
        """Find and return a _SwingModeWrapper for the given DP codes."""
        on_off = TuyaDPCodeBooleanWrapper.find_dpcode(
            device, XT_CLIMATE_SWING_MODE_ON_DPCODES, prefer_function=True
        )
        horizontal = TuyaDPCodeBooleanWrapper.find_dpcode(
            device, XT_CLIMATE_SWING_MODE_HORIZONTAL_DPCODES, prefer_function=True
        )
        vertical = TuyaDPCodeBooleanWrapper.find_dpcode(
            device, XT_CLIMATE_SWING_MODE_VERTICAL_DPCODES, prefer_function=True
        )
        if on_off or horizontal or vertical:
            options = [SWING_OFF]
            if on_off:
                options.append(SWING_ON)
            if horizontal:
                options.append(SWING_HORIZONTAL)
            if vertical:
                options.append(SWING_VERTICAL)
            return cls(
                on_off=on_off,
                horizontal=horizontal,
                vertical=vertical,
                options=options,
            )
        return None


def xt_get_default_definition(
    device: XTDevice, system_temperature_unit: TuyaUnitOfTemperature
) -> XTClimateDefinition:
    temperature_wrappers = _get_temperature_wrappers(device, system_temperature_unit)
    return XTClimateDefinition(
        current_humidity_wrapper=DPCodeRoundedIntegerWrapper.find_dpcode(
            device, XT_CLIMATE_CURRENT_HUMIDITY_DPCODES
        ),
        current_temperature_wrapper=temperature_wrappers[0],
        fan_mode_wrapper=DPCodeEnumWrapper.find_dpcode(
            device,
            XT_CLIMATE_FAN_SPEED_DPCODES,
            prefer_function=True,
        ),
        hvac_mode_wrapper=XTClimateHvacModeWrapper.find_dpcode(
            device, XT_CLIMATE_MODE_DPCODES, prefer_function=True
        ),
        preset_wrapper=DefaultPresetModeWrapper.find_dpcode(
            device, XT_CLIMATE_MODE_DPCODES, prefer_function=True
        ),
        set_temperature_wrapper=temperature_wrappers[1],
        swing_wrapper=SwingModeCompositeWrapper.find_dpcode(device),
        switch_wrapper=DPCodeBooleanWrapper.find_dpcode(
            device, XT_CLIMATE_SWITCH_DPCODES, prefer_function=True
        ),
        target_humidity_wrapper=DPCodeRoundedIntegerWrapper.find_dpcode(
            device, XT_CLIMATE_SET_HUMIDITY_DPCODES, prefer_function=True
        ),
        temperature_unit=temperature_wrappers[2],
        hvac_action_wrapper=DPCodeEnumWrapper.find_dpcode(
            device,
            XT_CLIMATE_HVAC_ACTION_DPCODES,  # type: ignore
            prefer_function=True,
        ),
    )


def _get_temperature_wrappers(
    device: XTDevice, system_temperature_unit: TuyaUnitOfTemperature
) -> tuple[
    DPCodeIntegerWrapper | None, DPCodeIntegerWrapper | None, TuyaUnitOfTemperature
]:
    """Get temperature wrappers for current and set temperatures."""
    # Get all possible temperature dpcodes
    temp_current = DPCodeIntegerWrapper.find_dpcode(
        device,
        XT_CLIMATE_CURRENT_CELSIUS_TEMPERATURE_DPCODES,  # type: ignore
    )
    temp_current_f = DPCodeIntegerWrapper.find_dpcode(
        device,
        XT_CLIMATE_CURRENT_FAHRENHEIT_TEMPERATURE_DPCODES,  # type: ignore
    )
    temp_set = DPCodeIntegerWrapper.find_dpcode(
        device,
        XT_CLIMATE_SET_CELSIUS_TEMPERATURE_DPCODES,
        prefer_function=True,  # type: ignore
    )
    temp_set_f = DPCodeIntegerWrapper.find_dpcode(
        device,
        XT_CLIMATE_SET_FAHRENHEIT_TEMPERATURE_DPCODES,
        prefer_function=True,  # type: ignore
    )

    # If there is a temp unit convert dpcode, override empty units
    if (
        temp_unit_convert := DPCodeEnumWrapper.find_dpcode(device, "temp_unit_convert")
    ) is not None:
        for wrapper in (temp_current, temp_current_f, temp_set, temp_set_f):
            if wrapper is not None and not wrapper.type_information.unit:
                wrapper.type_information.unit = temp_unit_convert.read_device_status(
                    device
                )

    # Get wrappers for celsius and fahrenheit
    # We need to check the unit of measurement
    current_celsius = _get_temperature_wrapper(
        [temp_current, temp_current_f], XT_CELSIUS_ALIASES
    )
    current_fahrenheit = _get_temperature_wrapper(
        [temp_current_f, temp_current], XT_FAHRENHEIT_ALIASES
    )
    set_celsius = _get_temperature_wrapper([temp_set, temp_set_f], XT_CELSIUS_ALIASES)
    set_fahrenheit = _get_temperature_wrapper(
        [temp_set_f, temp_set], XT_FAHRENHEIT_ALIASES
    )

    # Return early if we have the right wrappers for the system unit
    if system_temperature_unit == TuyaUnitOfTemperature.FAHRENHEIT:
        if (
            (current_fahrenheit and set_fahrenheit)
            or (current_fahrenheit and not set_celsius)
            or (set_fahrenheit and not current_celsius)
        ):
            return (
                current_fahrenheit,
                set_fahrenheit,
                TuyaUnitOfTemperature.FAHRENHEIT,
            )
    if (
        (current_celsius and set_celsius)
        or (current_celsius and not set_fahrenheit)
        or (set_celsius and not current_fahrenheit)
    ):
        return (
            current_celsius,
            set_celsius,
            TuyaUnitOfTemperature.CELSIUS,
        )

    # If we don't have the right wrappers, return whatever is available
    # and assume system unit
    if system_temperature_unit == TuyaUnitOfTemperature.FAHRENHEIT:
        return (
            temp_current_f or temp_current,
            temp_set_f or temp_set,
            TuyaUnitOfTemperature.FAHRENHEIT,
        )

    return (
        temp_current or temp_current_f,
        temp_set or temp_set_f,
        TuyaUnitOfTemperature.CELSIUS,
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya climate dynamically through Tuya discovery."""
    hass_data = entry.runtime_data
    this_platform = Platform.CLIMATE

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, XTClimateEntityDescription], dict[str, XTClimateEntityDescription]
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            CLIMATE_DESCRIPTIONS,
            entry.runtime_data.multi_manager,
            XTClimateEntityDescription,
            this_platform,
        ),
    )

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered Tuya climate."""
        if hass_data.manager is None:
            return None
        if restrict_dpcode is not None:
            return None
        entities: list[XTClimateEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if device_descriptor := XTEntityDescriptorManager.get_category_descriptors(
                    supported_descriptors, device.category
                ):
                    definition = xt_get_default_definition(
                        device=device,
                        system_temperature_unit=TUYA_HA_TO_TUYA_TEMPERATURE.get(
                            hass.config.units.temperature_unit,
                            TuyaUnitOfTemperature.CELSIUS,
                        ),
                    )
                    if definition.hvac_mode_wrapper is not None:
                        definition.hvac_mode_wrapper.remap_heat_cool_based_on_action_wrapper(
                            definition.hvac_action_wrapper
                        )
                    entities.append(
                        XTClimateEntity.get_entity_instance(
                            device=device,
                            device_manager=hass_data.manager,
                            description=device_descriptor,
                            definition=definition,
                        )
                    )
        async_add_entities(entities)

    hass_data.manager.register_device_descriptors(this_platform, supported_descriptors)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTClimateEntity(XTEntity, TuyaClimateEntity):
    """XT Climate Device."""

    class ControlDPCode(StrEnum):
        HVAC_MODE = "hvac_mode"  # HVAC mode
        CURRENT_TEMPERATURE = "current_temperature"  # Current temperature
        SET_TEMPERATURE = "set_temperature"  # Target temperature
        TEMPERATURE_UNIT = "temperature_unit"  # Which temperature unit is to be used
        CURRENT_HUMIDITY = "current_humidity"  # Current humidity
        SET_HUMIDITY = "set_humidity"  # Target humidity
        FAN_SPEED = "fan_speed"  # Fan speeds
        SWING_MODE_ON = "swing_mode_on"  # Activate swinging
        SWING_MODE_HORIZONTAL = "swing_mode_horizontal"  # Swing horizontaly
        SWING_MODE_VERTICAL = "swing_mode_vertical"  # Swing verticaly
        SWITCH_ON = "switch_on"  # Switch on device

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTClimateEntityDescription,
        definition: XTClimateDefinition,
    ) -> None:
        """Determine which values to use."""
        super(XTClimateEntity, self).__init__(
            device=device,
            device_manager=device_manager,  # type: ignore
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
        self._definition = definition
        self._hvac_action_wrapper = definition.hvac_action_wrapper
        self.device.set_preference(
            f"{XTDevice.XTDevicePreference.CLIMATE_DEVICE_ENTITY}",
            self,
        )
        self.configurable_properties = cast(
            XTClimateConfigurableProperties, self.get_configurable_properties()
        )

        # Re-Determine HVAC modes
        self._attr_hvac_modes = []
        if definition.hvac_mode_wrapper:
            self._attr_hvac_modes = [HVACMode.OFF]
            for tuya_mode in cast(
                list[TuyaClimateHVACMode], definition.hvac_mode_wrapper.options
            ):
                if (
                    ha_mode := MERGED_TUYALIB_TO_HA_HVACMODE_MAPPINGS.get(tuya_mode)
                ) and tuya_mode != HVACMode.OFF:
                    # OFF is always added first
                    self._attr_hvac_modes.append(ha_mode)

        elif definition.switch_wrapper:
            self._attr_hvac_modes = [
                HVACMode.OFF,
                description.switch_only_hvac_mode,
            ]

        # Determine preset modes (ignore if empty options)
        if definition.preset_wrapper and definition.preset_wrapper.options:
            for option in definition.preset_wrapper.options:
                if tuya_mode := MERGED_HVAC_TUYA_TO_TUYALIB.get(option):
                    if ha_mode := MERGED_TUYALIB_TO_HA_HVACMODE_MAPPINGS.get(tuya_mode):
                        if ha_mode not in self._attr_hvac_modes:
                            self._attr_hvac_modes.append(ha_mode)
            if isinstance(self._hvac_mode_wrapper, XTClimateHvacModeWrapper):
                if self._hvac_mode_wrapper.replace_heat_cool_with is not None:
                    ha_mode_replace_heat_cool_with = (
                        MERGED_TUYALIB_TO_HA_HVACMODE_MAPPINGS.get(
                            self._hvac_mode_wrapper.replace_heat_cool_with
                        )
                    )
                    if ha_mode_replace_heat_cool_with is not None:
                        if HVACMode.HEAT_COOL in self._attr_hvac_modes:
                            self._attr_hvac_modes.remove(HVACMode.HEAT_COOL)
                        if ha_mode_replace_heat_cool_with not in self._attr_hvac_modes:
                            self._attr_hvac_modes.append(ha_mode_replace_heat_cool_with)

    def get_configurable_properties_type(self) -> type[Any] | None:
        return XTClimateConfigurableProperties

    def get_configurable_properties_key(self) -> str | None:
        return "climate_configurable_properties"
    
    def refresh_configurable_properties(self):
        self.configurable_properties = cast(
            XTClimateConfigurableProperties, self.get_configurable_properties()
        )

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        current_temperature = super().current_temperature
        if (
            current_temperature is not None
            and self.configurable_properties is not None
            and self.configurable_properties.current_temperature_value_multiplicator
            is not None
        ):
            current_temperature *= (
                self.configurable_properties.current_temperature_value_multiplicator
            )
        return current_temperature

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        current_humidity = super().current_humidity
        if (
            current_humidity is not None
            and self.configurable_properties is not None
            and self.configurable_properties.current_humidity_value_multiplicator
            is not None
        ):
            current_humidity = int(
                current_humidity
                * self.configurable_properties.current_humidity_value_multiplicator
            )
        return current_humidity

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature currently set to be reached."""
        target_temperature = super().target_temperature
        if (
            target_temperature is not None
            and self.configurable_properties is not None
            and self.configurable_properties.target_temperature_value_multiplicator
            is not None
        ):
            target_temperature *= (
                self.configurable_properties.target_temperature_value_multiplicator
            )
        return target_temperature

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity currently set to be reached."""
        target_humidity = super().target_humidity
        if (
            target_humidity is not None
            and self.configurable_properties is not None
            and self.configurable_properties.target_humidity_value_multiplicator
            is not None
        ):
            target_humidity = int(
                target_humidity
                * self.configurable_properties.target_humidity_value_multiplicator
            )
        return target_humidity
    
    @property
    def min_temp(self) -> float: # type: ignore
        """Return the minimum temperature."""
        min_temp = super().min_temp
        if self.configurable_properties is not None and self.configurable_properties.target_temperature_value_multiplicator is not None:
            min_temp = min_temp * self.configurable_properties.target_temperature_value_multiplicator
        return min_temp

    @property
    def max_temp(self) -> float: # type: ignore
        """Return the maximum temperature."""
        max_temp = super().max_temp
        if self.configurable_properties is not None and self.configurable_properties.target_temperature_value_multiplicator is not None:
            max_temp = max_temp * self.configurable_properties.target_temperature_value_multiplicator
        return max_temp

    @property
    def min_humidity(self) -> float: # type: ignore
        """Return the minimum humidity."""
        min_humidity = super().min_humidity
        if self.configurable_properties is not None and self.configurable_properties.target_humidity_value_multiplicator is not None:
            min_humidity = min_humidity * self.configurable_properties.target_humidity_value_multiplicator
        return min_humidity

    @property
    def max_humidity(self) -> float: # type: ignore
        """Return the maximum humidity."""
        max_humidity = super().max_humidity
        if self.configurable_properties is not None and self.configurable_properties.target_humidity_value_multiplicator is not None:
            max_humidity = max_humidity * self.configurable_properties.target_humidity_value_multiplicator
        return max_humidity

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        if self.configurable_properties is not None and self.configurable_properties.target_humidity_value_multiplicator is not None:
            humidity = int(humidity / self.configurable_properties.target_humidity_value_multiplicator)
        await super().async_set_humidity(humidity=humidity)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs and self.configurable_properties is not None and self.configurable_properties.target_temperature_value_multiplicator is not None:
            kwargs[ATTR_TEMPERATURE] = kwargs[ATTR_TEMPERATURE] / self.configurable_properties.target_temperature_value_multiplicator
        await super().async_set_temperature(**kwargs)

    @property
    def hvac_action(self) -> HVACAction | None:  # type: ignore
        """Return the current running hvac operation if supported."""
        raw_value = self._read_wrapper(self._hvac_action_wrapper)
        if raw_value in XT_HVAC_ACTION_TO_HA:
            return XT_HVAC_ACTION_TO_HA[raw_value]
        return self._attr_hvac_action

    @property
    def preset_mode(self) -> str | None:
        """Return preset mode."""
        value = self._read_wrapper(self._preset_wrapper)
        return value

    @staticmethod
    def get_entity_instance(
        device: XTDevice,
        device_manager: MultiManager,
        description: XTClimateEntityDescription,
        definition: XTClimateDefinition,
    ) -> XTClimateEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(
                device=device,
                device_manager=device_manager,
                description=description,
                definition=definition,
            )
        return XTClimateEntity(
            device=device,
            device_manager=device_manager,
            description=XTClimateEntityDescription(**description.__dict__),
            definition=definition,
        )

    # @property
    # def target_temperature_step(self) -> float | None:
    #     """Return the target temperature step to use."""
    #     if (
    #         self.device_manager.config_entry.options
    #         and "device_settings" in self.device_manager.config_entry.options
    #         and self.device.id
    #         in self.device_manager.config_entry.options["device_settings"]
    #     ):
    #         return self.device_manager.config_entry.options["device_settings"][
    #             self.device.id
    #         ].get("target_temperature_step")
    #     return super().target_temperature_step
