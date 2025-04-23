"""Support for XT Climate."""

from __future__ import annotations

from dataclasses import dataclass


from homeassistant.components.climate import (
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .util import (
    append_dictionnaries
)

from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .const import TUYA_DISCOVERY_NEW, XTDPCode, DPType
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaClimateEntity,
    TuyaClimateEntityDescription,
    TuyaClimateHVACToHA,
)
from .entity import (
    XTEntity,
)

@dataclass(frozen=True, kw_only=True)
class XTClimateEntityDescription(TuyaClimateEntityDescription):
    """Describe an Tuya climate entity."""

    switch_only_hvac_mode: HVACMode


CLIMATE_DESCRIPTIONS: dict[str, XTClimateEntityDescription] = {
}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya climate dynamically through Tuya discovery."""
    hass_data = entry.runtime_data
    
    merged_descriptions = CLIMATE_DESCRIPTIONS
    for new_descriptor in entry.runtime_data.multi_manager.get_platform_descriptors_to_merge(Platform.CLIMATE):
        merged_descriptions = append_dictionnaries(merged_descriptions, new_descriptor)

    @callback
    def async_discover_device(device_map) -> None:
        """Discover and add a discovered Tuya climate."""
        entities: list[XTClimateEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if device and device.category in merged_descriptions:
                    entities.append(
                        XTClimateEntity(
                            device,
                            hass_data.manager,
                            XTClimateEntityDescription(**merged_descriptions[device.category].__dict__),
                            hass.config.units.temperature_unit,
                        )
                    )
        async_add_entities(entities)

    hass_data.manager.register_device_descriptors("climate_descriptions", merged_descriptions)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTClimateEntity(XTEntity, TuyaClimateEntity):
    """XT Climate Device."""

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTClimateEntityDescription,
        system_temperature_unit: UnitOfTemperature,
    ) -> None:
        """Determine which values to use."""
        super(XTClimateEntity, self).__init__(device, device_manager, description, system_temperature_unit)
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description

        # Determine HVAC modes
        self._attr_hvac_modes: list[HVACMode] = []
        self._hvac_to_tuya = {}
        if enum_type := self.find_dpcode(
            XTDPCode.MODE, dptype=DPType.ENUM, prefer_function=True
        ):
            self._attr_hvac_modes = [HVACMode.OFF]
            unknown_hvac_modes: list[str] = []
            for tuya_mode in enum_type.range:
                if tuya_mode in TuyaClimateHVACToHA:
                    ha_mode = TuyaClimateHVACToHA[tuya_mode]
                    if ha_mode != HVACMode.OFF:
                        if previous_ha_mode := self._hvac_to_tuya.get(ha_mode):
                            #This HVAC mode has more than one mode, add it to the presets
                            if previous_ha_mode not in unknown_hvac_modes:
                                unknown_hvac_modes.append(previous_ha_mode)
                            unknown_hvac_modes.append(tuya_mode)
                            continue
                    self._hvac_to_tuya[ha_mode] = tuya_mode
                    self._attr_hvac_modes.append(ha_mode)
                else:
                    unknown_hvac_modes.append(tuya_mode)
            
            #Clean presets that are in hvac_mode
            new_hvac_to_tuya = {}
            for ha_mode in self._hvac_to_tuya:
                if self._hvac_to_tuya[ha_mode] in unknown_hvac_modes:
                    self._attr_hvac_modes.remove(ha_mode)
                else:
                    new_hvac_to_tuya[ha_mode] = self._hvac_to_tuya[ha_mode]
            self._hvac_to_tuya = new_hvac_to_tuya
            if unknown_hvac_modes:  # Tuya modes are presets instead of hvac_modes
                if description.switch_only_hvac_mode not in self._attr_hvac_modes:
                    self._attr_hvac_modes.append(description.switch_only_hvac_mode)
                self._attr_preset_modes = unknown_hvac_modes
                self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE
        elif self.find_dpcode(XTDPCode.SWITCH, prefer_function=True):
            self._attr_hvac_modes = [
                HVACMode.OFF,
                description.switch_only_hvac_mode,
            ]
        self.device_manager.device_watcher.report_message(self.device.id, f"_hvac_to_tuya: {self._hvac_to_tuya} <=> _attr_hvac_modes: {self._attr_hvac_modes} <=> _attr_preset_modes: {self._attr_preset_modes}")