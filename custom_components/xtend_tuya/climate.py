"""Support for XT Climate."""

from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, cast
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
    SWING_BOTH,  # noqa: F401
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_ON,
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
    CROSS_CATEGORY_DEVICE_DESCRIPTOR,  # noqa: F401
    LOGGER,  # noqa: F401
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaClimateEntity,
    TuyaClimateEntityDescription,
    TuyaClimateHVACToHA,
    TuyaDPType,
    TuyaEnumTypeData,
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
    "hot": HVACMode.HEAT,
    "manual": HVACMode.HEAT_COOL,
    "smartcool": HVACMode.HEAT_COOL,
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
XT_CLIMATE_SET_CELSIUS_TEMPERATURE_DPCODES: tuple[XTDPCode, ...] = (XTDPCode.TEMP_SET,)
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

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTClimateEntityDescription,
        system_temperature_unit: UnitOfTemperature,
    ) -> XTClimateEntity:
        return XTClimateEntity(
            device=device,
            device_manager=device_manager,
            description=description,
            system_temperature_unit=system_temperature_unit,
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


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya climate dynamically through Tuya discovery."""
    hass_data = entry.runtime_data

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, XTClimateEntityDescription], dict[str, XTClimateEntityDescription]
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            CLIMATE_DESCRIPTIONS, entry.runtime_data.multi_manager, Platform.CLIMATE
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
                if device_descriptor := XTEntityDescriptorManager.get_category_descriptors(supported_descriptors, device.category):
                    entities.append(
                        XTClimateEntity.get_entity_instance(
                            device_descriptor,
                            device,
                            hass_data.manager,
                            hass.config.units.temperature_unit,
                        )
                    )
        async_add_entities(entities)

    hass_data.manager.register_device_descriptors(
        Platform.CLIMATE, supported_descriptors
    )
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
        system_temperature_unit: UnitOfTemperature,
    ) -> None:
        """Determine which values to use."""
        super(XTClimateEntity, self).__init__(
            device, device_manager, description, system_temperature_unit
        )
        super(XTEntity, self).__init__(device, device_manager, description, system_temperature_unit)  # type: ignore
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description
        self._attr_preset_modes = None
        self.control_dp_codes: dict[XTClimateEntity.ControlDPCode, XTDPCode] = {}
        self.swing_mode_enum_type: TuyaEnumTypeData | None = None
        # If both temperature values for celsius and fahrenheit are present,
        # use whatever the device is set to, with a fallback to celsius.
        prefered_temperature_unit = None
        if any(
            dpcode in device.status for dpcode in XT_CLIMATE_CURRENT_TEMPERATURE_DPCODES
        ) or any(
            dpcode in device.status for dpcode in XT_CLIMATE_SET_TEMPERATURE_DPCODES
        ):
            prefered_temperature_unit = UnitOfTemperature.CELSIUS
            if any(
                "f" in device.status[dpcode].lower()
                for dpcode in XT_CLIMATE_TEMPERATURE_UNIT_DPCODES
                if isinstance(device.status.get(dpcode), str)
            ):
                prefered_temperature_unit = UnitOfTemperature.FAHRENHEIT

        for dpcode in XT_CLIMATE_TEMPERATURE_UNIT_DPCODES:
            if dpcode in device.status:
                self.control_dp_codes[
                    XTClimateEntity.ControlDPCode.TEMPERATURE_UNIT
                ] = dpcode

        # Default to System Temperature Unit
        self._attr_temperature_unit = system_temperature_unit

        # Figure out current temperature, use preferred unit or what is available
        celsius_type = self.find_dpcode(
            XT_CLIMATE_CURRENT_CELSIUS_TEMPERATURE_DPCODES, dptype=TuyaDPType.INTEGER
        )
        fahrenheit_type = self.find_dpcode(
            XT_CLIMATE_CURRENT_FAHRENHEIT_TEMPERATURE_DPCODES, dptype=TuyaDPType.INTEGER
        )
        if fahrenheit_type and (
            prefered_temperature_unit == UnitOfTemperature.FAHRENHEIT
            or (
                prefered_temperature_unit == UnitOfTemperature.CELSIUS
                and not celsius_type
            )
        ):
            self.control_dp_codes[XTClimateEntity.ControlDPCode.CURRENT_TEMPERATURE] = (
                XTDPCode(fahrenheit_type.dpcode)
            )
            self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
            self._current_temperature = fahrenheit_type
        elif celsius_type:
            self.control_dp_codes[XTClimateEntity.ControlDPCode.CURRENT_TEMPERATURE] = (
                XTDPCode(celsius_type.dpcode)
            )
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS
            self._current_temperature = celsius_type

        # Figure out setting temperature, use preferred unit or what is available
        celsius_type = self.find_dpcode(
            XT_CLIMATE_SET_CELSIUS_TEMPERATURE_DPCODES,
            dptype=TuyaDPType.INTEGER,
            prefer_function=True,
            only_function=True,
        )
        fahrenheit_type = self.find_dpcode(
            XT_CLIMATE_SET_FAHRENHEIT_TEMPERATURE_DPCODES,
            dptype=TuyaDPType.INTEGER,
            prefer_function=True,
            only_function=True,
        )
        if fahrenheit_type and (
            prefered_temperature_unit == UnitOfTemperature.FAHRENHEIT
            or (
                prefered_temperature_unit == UnitOfTemperature.CELSIUS
                and not celsius_type
            )
        ):
            self._set_temperature = fahrenheit_type
        elif celsius_type:
            self._set_temperature = celsius_type

        # Get integer type data for the dpcode to set temperature, use
        # it to define min, max & step temperatures
        if self._set_temperature:
            self.control_dp_codes[XTClimateEntity.ControlDPCode.SET_TEMPERATURE] = (
                XTDPCode(self._set_temperature.dpcode)
            )
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
            self._attr_max_temp = self._set_temperature.max_scaled
            self._attr_min_temp = self._set_temperature.min_scaled
            self._attr_target_temperature_step = self._set_temperature.step_scaled

        # Determine HVAC modes
        self._attr_hvac_modes: list[HVACMode] = []
        self._hvac_to_tuya = {}
        if enum_type := self.find_dpcode(
            XT_CLIMATE_MODE_DPCODES,
            dptype=TuyaDPType.ENUM,
            prefer_function=True,
            only_function=True,
        ):
            self.control_dp_codes[XTClimateEntity.ControlDPCode.HVAC_MODE] = XTDPCode(
                enum_type.dpcode
            )
            self._attr_hvac_modes = [HVACMode.OFF]
            unknown_hvac_modes: list[str] = []
            for tuya_mode in enum_type.range:
                if tuya_mode in TuyaClimateHVACToHA:
                    ha_mode = TuyaClimateHVACToHA[tuya_mode]
                    if ha_mode.lower() != HVACMode.OFF.lower():
                        if previous_ha_mode := self._hvac_to_tuya.get(ha_mode):
                            # This HVAC mode has more than one mode, add it to the presets
                            if previous_ha_mode not in unknown_hvac_modes:
                                unknown_hvac_modes.append(previous_ha_mode)
                            unknown_hvac_modes.append(tuya_mode)
                            continue
                    self._hvac_to_tuya[ha_mode] = tuya_mode
                    self._attr_hvac_modes.append(ha_mode)
                else:
                    unknown_hvac_modes.append(tuya_mode)

            # Clean presets that are in hvac_mode
            new_hvac_to_tuya = {}
            for ha_mode in self._hvac_to_tuya:
                if self._hvac_to_tuya[ha_mode] in unknown_hvac_modes:
                    self._attr_hvac_modes.remove(HVACMode(ha_mode))
                else:
                    new_hvac_to_tuya[ha_mode] = self._hvac_to_tuya[ha_mode]
            self._hvac_to_tuya = new_hvac_to_tuya
            if unknown_hvac_modes:  # Tuya modes are presets instead of hvac_modes
                if description.switch_only_hvac_mode not in self._attr_hvac_modes:
                    self._attr_hvac_modes.append(description.switch_only_hvac_mode)
                self._attr_preset_modes = unknown_hvac_modes
                self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
        elif self.find_dpcode(
            XT_CLIMATE_SWITCH_DPCODES, prefer_function=True, only_function=True
        ):
            self._attr_hvac_modes = [
                HVACMode.OFF,
                description.switch_only_hvac_mode,
            ]

        # Determine dpcode to use for setting the humidity
        if int_type := self.find_dpcode(
            XT_CLIMATE_SET_HUMIDITY_DPCODES,
            dptype=TuyaDPType.INTEGER,
            prefer_function=True,
            only_function=True,
        ):
            self.control_dp_codes[XTClimateEntity.ControlDPCode.SET_HUMIDITY] = (
                XTDPCode(int_type.dpcode)
            )
            self._attr_supported_features |= ClimateEntityFeature.TARGET_HUMIDITY
            self._set_humidity = int_type
            self._attr_min_humidity = int(int_type.min_scaled)
            self._attr_max_humidity = int(int_type.max_scaled)

        # Determine dpcode to use for getting the current humidity
        self._current_humidity = self.find_dpcode(
            XT_CLIMATE_CURRENT_HUMIDITY_DPCODES, dptype=TuyaDPType.INTEGER
        )
        if self._current_humidity:
            self.control_dp_codes[XTClimateEntity.ControlDPCode.CURRENT_HUMIDITY] = (
                XTDPCode(self._current_humidity.dpcode)
            )

        # Determine fan modes
        if enum_type := self.find_dpcode(
            XT_CLIMATE_FAN_SPEED_DPCODES,
            dptype=TuyaDPType.ENUM,
            prefer_function=True,
            only_function=True,
        ):
            self.control_dp_codes[XTClimateEntity.ControlDPCode.FAN_SPEED] = XTDPCode(
                enum_type.dpcode
            )
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
            self._attr_fan_modes = enum_type.range

        # Determine swing modes
        if self.find_dpcode(
            XT_CLIMATE_SWING_MODE_DPCODES,
            prefer_function=True,
            only_function=True,
        ):
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE
            self._attr_swing_modes = [SWING_OFF]
            if dpcode := self.find_dpcode(
                XT_CLIMATE_SWING_MODE_ON_DPCODES,
                prefer_function=True,
                only_function=True,
            ):
                self.control_dp_codes[XTClimateEntity.ControlDPCode.SWING_MODE_ON] = (
                    XTDPCode(dpcode)
                )
                self.swing_mode_enum_type = self.find_dpcode(
                    dpcodes=dpcode, dptype=TuyaDPType.ENUM, prefer_function=True
                )
                self._attr_swing_modes.append(SWING_ON)

            if dpcode := self.find_dpcode(
                XT_CLIMATE_SWING_MODE_HORIZONTAL_DPCODES,
                prefer_function=True,
                only_function=True,
            ):
                self.control_dp_codes[
                    XTClimateEntity.ControlDPCode.SWING_MODE_HORIZONTAL
                ] = XTDPCode(dpcode)
                self._attr_swing_modes.append(SWING_HORIZONTAL)

            if dpcode := self.find_dpcode(
                XT_CLIMATE_SWING_MODE_VERTICAL_DPCODES,
                prefer_function=True,
                only_function=True,
            ):
                self.control_dp_codes[
                    XTClimateEntity.ControlDPCode.SWING_MODE_VERTICAL
                ] = XTDPCode(dpcode)
                self._attr_swing_modes.append(SWING_VERTICAL)

        for switch_dpcode in XT_CLIMATE_SWITCH_DPCODES:
            if switch_dpcode in self.device.function:
                self._attr_supported_features |= (
                    ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
                )
                self.control_dp_codes[XTClimateEntity.ControlDPCode.SWITCH_ON] = (
                    switch_dpcode
                )
                break

        # self.device_manager.device_watcher.report_message(self.device.id, f"_hvac_to_tuya: {self._hvac_to_tuya if hasattr(self, "_hvac_to_tuya") else "NONE"} <=> _attr_hvac_modes: {self._attr_hvac_modes if hasattr(self, "_attr_hvac_modes") else "NONE"} <=> _attr_preset_modes: {self._attr_preset_modes if hasattr(self, "_attr_preset_modes") else "NONE"}")

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        commands = []
        if dpcode_hvac_mode := self.control_dp_codes.get(
            XTClimateEntity.ControlDPCode.HVAC_MODE
        ):
            if dpcode_switch := self.control_dp_codes.get(
                XTClimateEntity.ControlDPCode.SWITCH_ON
            ):
                commands.append(
                    {"code": dpcode_switch, "value": hvac_mode != HVACMode.OFF}
                )
            if hvac_mode in self._hvac_to_tuya:
                commands.append(
                    {"code": dpcode_hvac_mode, "value": self._hvac_to_tuya[hvac_mode]}
                )
        else:
            # This is a switch only HVAC (no selection of cool/heat/dry)
            if dpcode_switch := self.control_dp_codes.get(
                XTClimateEntity.ControlDPCode.SWITCH_ON
            ):
                commands.append(
                    {"code": dpcode_switch, "value": hvac_mode != HVACMode.OFF}
                )
        if len(commands) > 0:
            self._send_command(commands)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new target preset mode."""
        if dpcode_hvac_mode := self.control_dp_codes.get(
            XTClimateEntity.ControlDPCode.HVAC_MODE
        ):
            self._send_command([{"code": dpcode_hvac_mode, "value": preset_mode}])

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if dpcode_fan_mode := self.control_dp_codes.get(
            XTClimateEntity.ControlDPCode.FAN_SPEED
        ):
            self._send_command([{"code": dpcode_fan_mode, "value": fan_mode}])

    def get_swing_mode_on_value(self, bool_swing: bool) -> bool | str:
        if self.swing_mode_enum_type is not None:
            for allowed_value in self.swing_mode_enum_type.range:
                if (
                    XT_CLIMATE_SWING_MODE_ENUM_VALUE_MAPPING.get(allowed_value.lower())
                    is bool_swing
                ):
                    return allowed_value
        return bool_swing

    def is_swing_mode_on(self) -> bool:
        swing_mode_status_value = self.device.status.get(
            self.control_dp_codes.get(XTClimateEntity.ControlDPCode.SWING_MODE_ON, "")
        )
        if self.swing_mode_enum_type is not None:
            return XT_CLIMATE_SWING_MODE_ENUM_VALUE_MAPPING.get(
                str(swing_mode_status_value).lower(), bool(swing_mode_status_value)
            )
        return bool(swing_mode_status_value)

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        commands: list[dict[str, Any]] = []
        if dpcode_swing := self.control_dp_codes.get(
            XTClimateEntity.ControlDPCode.SWING_MODE_ON
        ):
            commands.append(
                {
                    "code": dpcode_swing,
                    "value": self.get_swing_mode_on_value(swing_mode != SWING_OFF),
                }
            )
        if dpcode_swing_horizontal := self.control_dp_codes.get(
            XTClimateEntity.ControlDPCode.SWING_MODE_HORIZONTAL
        ):
            commands.append(
                {
                    "code": dpcode_swing_horizontal,
                    "value": swing_mode in (SWING_BOTH, SWING_HORIZONTAL),
                }
            )
        if dpcode_swing_vertical := self.control_dp_codes.get(
            XTClimateEntity.ControlDPCode.SWING_MODE_VERTICAL
        ):
            commands.append(
                {
                    "code": dpcode_swing_vertical,
                    "value": swing_mode in (SWING_BOTH, SWING_VERTICAL),
                }
            )
        if len(commands) > 0:
            self._send_command(commands)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac mode."""
        # If the switch off, hvac mode is off as well. Unless the switch
        # the switch is on or doesn't exists of course...
        if not self.device.status.get(
            self.control_dp_codes.get(XTClimateEntity.ControlDPCode.SWITCH_ON, ""), True
        ):
            return HVACMode.OFF

        if (
            self.control_dp_codes.get(XTClimateEntity.ControlDPCode.HVAC_MODE, "")
            not in self.device.function
        ):
            if self.device.status.get(
                self.control_dp_codes.get(XTClimateEntity.ControlDPCode.SWITCH_ON, ""),
                False,
            ):
                return self.entity_description.switch_only_hvac_mode
            return HVACMode.OFF

        if (
            (
                mode := self.device.status.get(
                    self.control_dp_codes.get(
                        XTClimateEntity.ControlDPCode.HVAC_MODE, ""
                    )
                )
            )
            is not None
        ) is not None and mode in MERGED_HVAC_TO_HA:
            return MERGED_HVAC_TO_HA[mode]

        # If the switch is on, and the mode does not match any hvac mode.
        if self.device.status.get(
            self.control_dp_codes.get(XTClimateEntity.ControlDPCode.SWITCH_ON, ""),
            False,
        ):
            return self.entity_description.switch_only_hvac_mode

        return HVACMode.OFF

    @property
    def preset_mode(self) -> str | None:
        """Return preset mode."""
        if (
            self.control_dp_codes.get(XTClimateEntity.ControlDPCode.HVAC_MODE, "")
            not in self.device.function
        ):
            return None

        mode = self.device.status.get(
            self.control_dp_codes.get(XTClimateEntity.ControlDPCode.HVAC_MODE, "")
        )
        if mode in MERGED_HVAC_TO_HA:
            return None

        return mode

    @property
    def fan_mode(self) -> str | None:
        """Return fan mode."""
        return self.device.status.get(
            self.control_dp_codes.get(XTClimateEntity.ControlDPCode.FAN_SPEED, "")
        )

    @property
    def swing_mode(self) -> str:
        """Return swing mode."""
        horizontal = self.device.status.get(
            self.control_dp_codes.get(
                XTClimateEntity.ControlDPCode.SWING_MODE_HORIZONTAL, ""
            )
        )
        vertical = self.device.status.get(
            self.control_dp_codes.get(
                XTClimateEntity.ControlDPCode.SWING_MODE_VERTICAL, ""
            )
        )
        if horizontal and vertical:
            return SWING_BOTH
        if horizontal:
            return SWING_HORIZONTAL
        if vertical:
            return SWING_VERTICAL

        if self.is_swing_mode_on():
            return SWING_ON

        return SWING_OFF

    def turn_on(self) -> None:
        """Turn the device on, retaining current HVAC (if supported)."""
        if dpcode_switch := self.control_dp_codes.get(
            XTClimateEntity.ControlDPCode.SWITCH_ON
        ):
            self._send_command([{"code": dpcode_switch, "value": True}])

    def turn_off(self) -> None:
        """Turn the device on, retaining current HVAC (if supported)."""
        if dpcode_switch := self.control_dp_codes.get(
            XTClimateEntity.ControlDPCode.SWITCH_ON
        ):
            self._send_command([{"code": dpcode_switch, "value": False}])

    def _send_command(self, commands: list[dict[str, Any]]) -> None:
        """Send command to the device."""
        self.device_manager.send_commands(self.device.id, commands)

    @staticmethod
    def get_entity_instance(
        description: XTClimateEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
        system_temperature_unit: UnitOfTemperature,
    ) -> XTClimateEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(
                device, device_manager, description, system_temperature_unit
            )
        return XTClimateEntity(
            device,
            device_manager,
            XTClimateEntityDescription(**description.__dict__),
            system_temperature_unit,
        )
