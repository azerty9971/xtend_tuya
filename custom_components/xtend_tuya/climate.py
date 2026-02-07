"""Support for XT Climate."""

from __future__ import annotations
import collections
from dataclasses import dataclass
from enum import StrEnum
from typing import cast, Self
from homeassistant.components.climate.const import (
    HVACMode,
    SWING_OFF,
    SWING_ON,
    SWING_HORIZONTAL,
    SWING_VERTICAL,
)
from homeassistant.const import UnitOfTemperature, Platform
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
    TuyaClimateHVACToHA,
    TuyaDPCodeIntegerWrapper,
    TuyaDPCodeEnumWrapper,
    TuyaDPCodeBooleanWrapper,
    TuyaClimateRoundedIntegerWrapper,
    tuya_climate_get_temperature_wrapper,
    TuyaClimateSwingModeWrapper,
    TuyaCustomerDevice,
    TuyaDeviceWrapper,
    TuyaClimatePresetWrapper,
    TuyaClimateHvacModeWrapper,
    TuyaEnumTypeInformation,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)

XT_HVAC_TO_HA = {
    "auto": HVACMode.AUTO,
    "cold": HVACMode.COOL,
    "cool": HVACMode.COOL,
    "dehumidify": HVACMode.DRY,
    "freeze": HVACMode.COOL,
    "heat": HVACMode.HEAT,
    "home": HVACMode.HEAT_COOL,
    "hot": HVACMode.HEAT,
    "manual": HVACMode.HEAT_COOL,
    "smartcool": HVACMode.HEAT_COOL,
    "temporary": HVACMode.HEAT_COOL,
    "wet": HVACMode.DRY,
    "wind": HVACMode.FAN_ONLY,
}

MERGED_HVAC_TO_HA: dict[str, HVACMode] = append_dictionnaries(
    XT_HVAC_TO_HA, TuyaClimateHVACToHA
)

XT_CLIMATE_MODE_DPCODES: tuple[XTDPCode, ...] = (
    XTDPCode.MODE,
    XTDPCode.MODE1,
)
XT_CLIMATE_CURRENT_NON_UNIT_TEMPERATURE_DPCODES: tuple[XTDPCode, ...] = (
    XTDPCode.GET_TEMP,
)
XT_CLIMATE_CURRENT_CELSIUS_TEMPERATURE_DPCODES: tuple[XTDPCode, ...] = (
    XTDPCode.TEMP_CURRENT,
    XTDPCode.UPPER_TEMP,
)
XT_CLIMATE_CURRENT_FAHRENHEIT_TEMPERATURE_DPCODES: tuple[XTDPCode, ...] = (
    XTDPCode.TEMP_CURRENT_F,
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
    XTDPCode.TEMPSET,
)
XT_CLIMATE_SET_FAHRENHEIT_TEMPERATURE_DPCODES: tuple[XTDPCode, ...] = (
    XTDPCode.TEMP_SET_F,
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
    XTDPCode.POWER,
    XTDPCode.POWER2,
)


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
        *,
        current_humidity_wrapper: TuyaClimateRoundedIntegerWrapper | None,
        current_temperature_wrapper: TuyaDPCodeIntegerWrapper | None,
        fan_mode_wrapper: TuyaDPCodeEnumWrapper | None,
        preset_wrapper: TuyaDeviceWrapper[str] | None,
        hvac_mode_wrapper: TuyaDPCodeEnumWrapper | None,
        set_temperature_wrapper: TuyaDPCodeIntegerWrapper | None,
        swing_wrapper: TuyaClimateSwingModeWrapper | None,
        switch_wrapper: TuyaDPCodeBooleanWrapper | None,
        target_humidity_wrapper: TuyaClimateRoundedIntegerWrapper | None,
        temperature_unit: UnitOfTemperature,
    ) -> XTClimateEntity:
        return XTClimateEntity(
            device=device,
            device_manager=device_manager,
            description=XTClimateEntityDescription(**description.__dict__),
            current_humidity_wrapper=current_humidity_wrapper,
            current_temperature_wrapper=current_temperature_wrapper,
            fan_mode_wrapper=fan_mode_wrapper,
            preset_wrapper=preset_wrapper,
            hvac_mode_wrapper=hvac_mode_wrapper,
            set_temperature_wrapper=set_temperature_wrapper,
            swing_wrapper=swing_wrapper,
            switch_wrapper=switch_wrapper,
            target_humidity_wrapper=target_humidity_wrapper,
            temperature_unit=temperature_unit,
        )


CLIMATE_DESCRIPTIONS: dict[str, XTClimateEntityDescription] = {
    "cs": XTClimateEntityDescription(
        key="cs",
        switch_only_hvac_mode=HVACMode.DRY,
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

def _filter_hvac_mode_mappings(tuya_range: list[str]) -> dict[str, HVACMode | None]:
    """Filter TUYA_HVAC_TO_HA modes that are not in the range.

    If multiple Tuya modes map to the same HA mode, set the mapping to None to avoid
    ambiguity when converting back from HA to Tuya modes.
    """
    modes_in_range = {
        tuya_mode: XT_HVAC_TO_HA.get(tuya_mode) for tuya_mode in tuya_range
    }
    modes_occurrences = collections.Counter(modes_in_range.values())
    for key, value in modes_in_range.items():
        if value is not None and modes_occurrences[value] > 1:
            modes_in_range[key] = None
    return modes_in_range

class XTClimatePresetWrapper(TuyaClimatePresetWrapper):
    def __init__(self, dpcode: str, type_information: TuyaEnumTypeInformation) -> None:
        """Init _PresetWrapper."""
        super().__init__(dpcode, type_information)
        mappings = _filter_hvac_mode_mappings(type_information.range)
        self.options = [
            tuya_mode for tuya_mode, ha_mode in mappings.items() if ha_mode is None
        ]
    
    def read_device_status(self, device: TuyaCustomerDevice) -> str | None:
        """Read the device status."""
        if (raw := super(TuyaClimatePresetWrapper, self).read_device_status(device)) in XT_HVAC_TO_HA:
            return None
        return raw

class XTClimateHvacModeWrapper(TuyaClimateHvacModeWrapper):
    def __init__(self, dpcode: str, type_information: TuyaEnumTypeInformation) -> None:
        """Init _HvacModeWrapper."""
        super().__init__(dpcode, type_information)
        self._mappings = _filter_hvac_mode_mappings(type_information.range)
        self.options = [
            ha_mode for ha_mode in self._mappings.values() if ha_mode is not None
        ]
    
    def read_device_status(self, device: TuyaCustomerDevice) -> HVACMode | None:
        """Read the device status."""
        if (raw := super(TuyaClimateHvacModeWrapper, self).read_device_status(device)) not in XT_HVAC_TO_HA:
            return None
        return XT_HVAC_TO_HA[raw]

class XTClimateSwingModeWrapper(TuyaClimateSwingModeWrapper):
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


def _get_temperature_wrappers(
    device: XTDevice, system_temperature_unit: UnitOfTemperature
) -> tuple[
    TuyaDPCodeIntegerWrapper | None, TuyaDPCodeIntegerWrapper | None, UnitOfTemperature
]:
    """Get temperature wrappers for current and set temperatures."""
    # Get all possible temperature dpcodes
    temp_current = TuyaDPCodeIntegerWrapper.find_dpcode(
        device,
        XT_CLIMATE_CURRENT_CELSIUS_TEMPERATURE_DPCODES,  # type: ignore
    )
    temp_current_f = TuyaDPCodeIntegerWrapper.find_dpcode(
        device,
        XT_CLIMATE_CURRENT_FAHRENHEIT_TEMPERATURE_DPCODES,  # type: ignore
    )
    temp_set = TuyaDPCodeIntegerWrapper.find_dpcode(
        device,
        XT_CLIMATE_SET_CELSIUS_TEMPERATURE_DPCODES,
        prefer_function=True,  # type: ignore
    )
    temp_set_f = TuyaDPCodeIntegerWrapper.find_dpcode(
        device,
        XT_CLIMATE_SET_FAHRENHEIT_TEMPERATURE_DPCODES,
        prefer_function=True,  # type: ignore
    )

    # Get wrappers for celsius and fahrenheit
    # We need to check the unit of measurement
    current_celsius = tuya_climate_get_temperature_wrapper(
        [temp_current, temp_current_f], XT_CELSIUS_ALIASES
    )
    current_fahrenheit = tuya_climate_get_temperature_wrapper(
        [temp_current_f, temp_current], XT_FAHRENHEIT_ALIASES
    )
    set_celsius = tuya_climate_get_temperature_wrapper(
        [temp_set, temp_set_f], XT_CELSIUS_ALIASES
    )
    set_fahrenheit = tuya_climate_get_temperature_wrapper(
        [temp_set_f, temp_set], XT_FAHRENHEIT_ALIASES
    )

    # Return early if we have the right wrappers for the system unit
    if system_temperature_unit == UnitOfTemperature.FAHRENHEIT:
        if (
            (current_fahrenheit and set_fahrenheit)
            or (current_fahrenheit and not set_celsius)
            or (set_fahrenheit and not current_celsius)
        ):
            return current_fahrenheit, set_fahrenheit, UnitOfTemperature.FAHRENHEIT
    if (
        (current_celsius and set_celsius)
        or (current_celsius and not set_fahrenheit)
        or (set_celsius and not current_fahrenheit)
    ):
        return current_celsius, set_celsius, UnitOfTemperature.CELSIUS

    # If we don't have the right wrappers, return whatever is available
    # and assume system unit
    if system_temperature_unit == UnitOfTemperature.FAHRENHEIT:
        return (
            temp_current_f or temp_current,
            temp_set_f or temp_set,
            UnitOfTemperature.FAHRENHEIT,
        )

    return (
        temp_current or temp_current_f,
        temp_set or temp_set_f,
        UnitOfTemperature.CELSIUS,
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
    LOGGER.warning(f"Supported climate descriptors: {supported_descriptors}")

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
                    temperature_wrappers = _get_temperature_wrappers(
                        device, hass.config.units.temperature_unit
                    )
                    entities.append(
                        XTClimateEntity.get_entity_instance(
                            device_descriptor,
                            device,
                            hass_data.manager,
                            current_humidity_wrapper=TuyaClimateRoundedIntegerWrapper.find_dpcode(
                                device,
                                XT_CLIMATE_CURRENT_HUMIDITY_DPCODES,  # type: ignore
                            ),
                            current_temperature_wrapper=temperature_wrappers[0],
                            fan_mode_wrapper=TuyaDPCodeEnumWrapper.find_dpcode(
                                device,
                                XT_CLIMATE_FAN_SPEED_DPCODES,  # type: ignore
                                prefer_function=True,
                            ),
                            preset_wrapper=XTClimatePresetWrapper.find_dpcode(
                                device,
                                XT_CLIMATE_MODE_DPCODES,
                                prefer_function=True,
                            ),
                            hvac_mode_wrapper=XTClimateHvacModeWrapper.find_dpcode(
                                device,
                                XT_CLIMATE_MODE_DPCODES,  # type: ignore
                                prefer_function=True,
                            ),
                            set_temperature_wrapper=temperature_wrappers[1],
                            swing_wrapper=XTClimateSwingModeWrapper.find_dpcode(
                                device,
                            ),
                            switch_wrapper=TuyaDPCodeBooleanWrapper.find_dpcode(
                                device,
                                XT_CLIMATE_SWITCH_DPCODES,  # type: ignore
                                prefer_function=True,
                            ),
                            target_humidity_wrapper=TuyaClimateRoundedIntegerWrapper.find_dpcode(
                                device,
                                XT_CLIMATE_SET_HUMIDITY_DPCODES,  # type: ignore
                                prefer_function=True,
                            ),
                            temperature_unit=temperature_wrappers[2],
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
        *,
        current_humidity_wrapper: TuyaClimateRoundedIntegerWrapper | None,
        current_temperature_wrapper: TuyaDPCodeIntegerWrapper | None,
        fan_mode_wrapper: TuyaDPCodeEnumWrapper | None,
        preset_wrapper: TuyaDeviceWrapper[str] | None,
        hvac_mode_wrapper: TuyaDPCodeEnumWrapper | None,
        set_temperature_wrapper: TuyaDPCodeIntegerWrapper | None,
        swing_wrapper: TuyaClimateSwingModeWrapper | None,
        switch_wrapper: TuyaDPCodeBooleanWrapper | None,
        target_humidity_wrapper: TuyaClimateRoundedIntegerWrapper | None,
        temperature_unit: UnitOfTemperature,
    ) -> None:
        """Determine which values to use."""
        device_manager.device_watcher.report_message(
            device.id,
            f"Creating XTClimateEntity for device {device.name} ({device.id}), wrappers: cur_temp({current_temperature_wrapper.dpcode if current_temperature_wrapper else 'None'}), set_temp({set_temperature_wrapper.dpcode if set_temperature_wrapper else 'None'}), hvac_mode({hvac_mode_wrapper.dpcode if hvac_mode_wrapper else 'None'}), fan_mode({fan_mode_wrapper.dpcode if fan_mode_wrapper else 'None'})",
        )
        super(XTClimateEntity, self).__init__(device, device_manager, description)
        super(XTEntity, self).__init__(
            device,
            device_manager,  # type: ignore
            description,
            current_humidity_wrapper=current_humidity_wrapper,
            current_temperature_wrapper=current_temperature_wrapper,
            fan_mode_wrapper=fan_mode_wrapper,
            preset_wrapper=preset_wrapper,
            hvac_mode_wrapper=hvac_mode_wrapper,
            set_temperature_wrapper=set_temperature_wrapper,
            swing_wrapper=swing_wrapper,
            switch_wrapper=switch_wrapper,
            target_humidity_wrapper=target_humidity_wrapper,
            temperature_unit=temperature_unit,
        )
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description

    @staticmethod
    def get_entity_instance(
        description: XTClimateEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
        *,
        current_humidity_wrapper: TuyaClimateRoundedIntegerWrapper | None,
        current_temperature_wrapper: TuyaDPCodeIntegerWrapper | None,
        fan_mode_wrapper: TuyaDPCodeEnumWrapper | None,
        preset_wrapper: TuyaDeviceWrapper[str] | None,
        hvac_mode_wrapper: TuyaDPCodeEnumWrapper | None,
        set_temperature_wrapper: TuyaDPCodeIntegerWrapper | None,
        swing_wrapper: TuyaClimateSwingModeWrapper | None,
        switch_wrapper: TuyaDPCodeBooleanWrapper | None,
        target_humidity_wrapper: TuyaClimateRoundedIntegerWrapper | None,
        temperature_unit: UnitOfTemperature,
    ) -> XTClimateEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(
                device,
                device_manager,
                description,
                current_humidity_wrapper=current_humidity_wrapper,
                current_temperature_wrapper=current_temperature_wrapper,
                fan_mode_wrapper=fan_mode_wrapper,
                preset_wrapper=preset_wrapper,
                hvac_mode_wrapper=hvac_mode_wrapper,
                set_temperature_wrapper=set_temperature_wrapper,
                swing_wrapper=swing_wrapper,
                switch_wrapper=switch_wrapper,
                target_humidity_wrapper=target_humidity_wrapper,
                temperature_unit=temperature_unit,
            )
        return XTClimateEntity(
            device,
            device_manager,
            XTClimateEntityDescription(**description.__dict__),
            current_humidity_wrapper=current_humidity_wrapper,
            current_temperature_wrapper=current_temperature_wrapper,
            fan_mode_wrapper=fan_mode_wrapper,
            preset_wrapper=preset_wrapper,
            hvac_mode_wrapper=hvac_mode_wrapper,
            set_temperature_wrapper=set_temperature_wrapper,
            swing_wrapper=swing_wrapper,
            switch_wrapper=switch_wrapper,
            target_humidity_wrapper=target_humidity_wrapper,
            temperature_unit=temperature_unit,
        )
