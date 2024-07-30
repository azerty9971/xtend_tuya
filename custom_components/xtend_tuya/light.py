"""Support for the Tuya lights."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, cast

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
    filter_supported_color_modes,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .multi_manager import XTConfigEntry
from .base import IntegerTypeData, TuyaEntity
from .const import TUYA_DISCOVERY_NEW, DPCode, DPType, WorkMode
from .util import remap_value


@dataclass
class ColorTypeData:
    """Color Type Data."""

    h_type: IntegerTypeData
    s_type: IntegerTypeData
    v_type: IntegerTypeData


DEFAULT_COLOR_TYPE_DATA = ColorTypeData(
    h_type=IntegerTypeData(DPCode.COLOUR_DATA_HSV, min=1, scale=0, max=360, step=1),
    s_type=IntegerTypeData(DPCode.COLOUR_DATA_HSV, min=1, scale=0, max=255, step=1),
    v_type=IntegerTypeData(DPCode.COLOUR_DATA_HSV, min=1, scale=0, max=255, step=1),
)

DEFAULT_COLOR_TYPE_DATA_V2 = ColorTypeData(
    h_type=IntegerTypeData(DPCode.COLOUR_DATA_HSV, min=1, scale=0, max=360, step=1),
    s_type=IntegerTypeData(DPCode.COLOUR_DATA_HSV, min=1, scale=0, max=1000, step=1),
    v_type=IntegerTypeData(DPCode.COLOUR_DATA_HSV, min=1, scale=0, max=1000, step=1),
)


@dataclass(frozen=True)
class TuyaLightEntityDescription(LightEntityDescription):
    """Describe an Tuya light entity."""

    brightness_max: DPCode | None = None
    brightness_min: DPCode | None = None
    brightness: DPCode | tuple[DPCode, ...] | None = None
    color_data: DPCode | tuple[DPCode, ...] | None = None
    color_mode: DPCode | None = None
    color_temp: DPCode | tuple[DPCode, ...] | None = None
    default_color_type: ColorTypeData = field(
        default_factory=lambda: DEFAULT_COLOR_TYPE_DATA
    )


LIGHTS: dict[str, tuple[TuyaLightEntityDescription, ...]] = {
}


@dataclass
class ColorData:
    """Color Data."""

    type_data: ColorTypeData
    h_value: int
    s_value: int
    v_value: int

    @property
    def hs_color(self) -> tuple[float, float]:
        """Get the HS value from this color data."""
        return (
            self.type_data.h_type.remap_value_to(self.h_value, 0, 360),
            self.type_data.s_type.remap_value_to(self.s_value, 0, 100),
        )

    @property
    def brightness(self) -> int:
        """Get the brightness value from this color data."""
        return round(self.type_data.v_type.remap_value_to(self.v_value, 0, 255))


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up tuya light dynamically through tuya discovery."""
    hass_data = entry.runtime_data

    @callback
    def async_discover_device(device_map):
        """Discover and add a discovered tuya light."""
        entities: list[TuyaLightEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            device = hass_data.manager.device_map[device_id]
            if descriptions := LIGHTS.get(device.category):
                entities.extend(
                    TuyaLightEntity(device, hass_data.manager, description)
                    for description in descriptions
                    if description.key in device.status
                )

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors("lights", LIGHTS)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaLightEntity(TuyaEntity, LightEntity):
    """Tuya light device."""

    entity_description: TuyaLightEntityDescription

    _brightness_max: IntegerTypeData | None = None
    _brightness_min: IntegerTypeData | None = None
    _brightness: IntegerTypeData | None = None
    _color_data_dpcode: DPCode | None = None
    _color_data_type: ColorTypeData | None = None
    _color_mode: DPCode | None = None
    _color_temp: IntegerTypeData | None = None
    _fixed_color_mode: ColorMode | None = None

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: TuyaLightEntityDescription,
    ) -> None:
        """Init TuyaHaLight."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"
        color_modes: set[ColorMode] = {ColorMode.ONOFF}

        # Determine DPCodes
        self._color_mode_dpcode = self.find_dpcode(
            description.color_mode, prefer_function=True
        )

        if int_type := self.find_dpcode(
            description.brightness, dptype=DPType.INTEGER, prefer_function=True
        ):
            self._brightness = int_type
            color_modes.add(ColorMode.BRIGHTNESS)
            self._brightness_max = self.find_dpcode(
                description.brightness_max, dptype=DPType.INTEGER
            )
            self._brightness_min = self.find_dpcode(
                description.brightness_min, dptype=DPType.INTEGER
            )

        if int_type := self.find_dpcode(
            description.color_temp, dptype=DPType.INTEGER, prefer_function=True
        ):
            self._color_temp = int_type
            color_modes.add(ColorMode.COLOR_TEMP)

        if (
            dpcode := self.find_dpcode(description.color_data, prefer_function=True)
        ) and self.get_dptype(dpcode) == DPType.JSON:
            self._color_data_dpcode = dpcode
            color_modes.add(ColorMode.HS)
            if dpcode in self.device.function:
                values = cast(str, self.device.function[dpcode].values)
            else:
                values = self.device.status_range[dpcode].values

            # Fetch color data type information
            if function_data := json.loads(values):
                self._color_data_type = ColorTypeData(
                    h_type=IntegerTypeData(dpcode, **function_data["h"]),
                    s_type=IntegerTypeData(dpcode, **function_data["s"]),
                    v_type=IntegerTypeData(dpcode, **function_data["v"]),
                )
            else:
                # If no type is found, use a default one
                self._color_data_type = self.entity_description.default_color_type
                if self._color_data_dpcode == DPCode.COLOUR_DATA_V2 or (
                    self._brightness and self._brightness.max > 255
                ):
                    self._color_data_type = DEFAULT_COLOR_TYPE_DATA_V2

        self._attr_supported_color_modes = filter_supported_color_modes(color_modes)
        if len(self._attr_supported_color_modes) == 1:
            # If the light supports only a single color mode, set it now
            self._fixed_color_mode = next(iter(self._attr_supported_color_modes))

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self.device.status.get(self.entity_description.key, False)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on or control the light."""
        commands = [{"code": self.entity_description.key, "value": True}]

        if self._color_temp and ATTR_COLOR_TEMP in kwargs:
            if self._color_mode_dpcode:
                commands += [
                    {
                        "code": self._color_mode_dpcode,
                        "value": WorkMode.WHITE,
                    },
                ]

            commands += [
                {
                    "code": self._color_temp.dpcode,
                    "value": round(
                        self._color_temp.remap_value_from(
                            kwargs[ATTR_COLOR_TEMP],
                            self.min_mireds,
                            self.max_mireds,
                            reverse=True,
                        )
                    ),
                },
            ]

        if self._color_data_type and (
            ATTR_HS_COLOR in kwargs
            or (
                ATTR_BRIGHTNESS in kwargs
                and self.color_mode == ColorMode.HS
                and ATTR_COLOR_TEMP not in kwargs
            )
        ):
            if self._color_mode_dpcode:
                commands += [
                    {
                        "code": self._color_mode_dpcode,
                        "value": WorkMode.COLOUR,
                    },
                ]

            if not (brightness := kwargs.get(ATTR_BRIGHTNESS)):
                brightness = self.brightness or 0

            if not (color := kwargs.get(ATTR_HS_COLOR)):
                color = self.hs_color or (0, 0)

            commands += [
                {
                    "code": self._color_data_dpcode,
                    "value": json.dumps(
                        {
                            "h": round(
                                self._color_data_type.h_type.remap_value_from(
                                    color[0], 0, 360
                                )
                            ),
                            "s": round(
                                self._color_data_type.s_type.remap_value_from(
                                    color[1], 0, 100
                                )
                            ),
                            "v": round(
                                self._color_data_type.v_type.remap_value_from(
                                    brightness
                                )
                            ),
                        }
                    ),
                },
            ]

        elif ATTR_BRIGHTNESS in kwargs and self._brightness:
            brightness = kwargs[ATTR_BRIGHTNESS]

            # If there is a min/max value, the brightness is actually limited.
            # Meaning it is actually not on a 0-255 scale.
            if (
                self._brightness_max is not None
                and self._brightness_min is not None
                and (
                    brightness_max := self.device.status.get(
                        self._brightness_max.dpcode
                    )
                )
                is not None
                and (
                    brightness_min := self.device.status.get(
                        self._brightness_min.dpcode
                    )
                )
                is not None
            ):
                # Remap values onto our scale
                brightness_max = self._brightness_max.remap_value_to(brightness_max)
                brightness_min = self._brightness_min.remap_value_to(brightness_min)

                # Remap the brightness value from their min-max to our 0-255 scale
                brightness = remap_value(
                    brightness,
                    to_min=brightness_min,
                    to_max=brightness_max,
                )

            commands += [
                {
                    "code": self._brightness.dpcode,
                    "value": round(self._brightness.remap_value_from(brightness)),
                },
            ]

        self._send_command(commands)

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        self._send_command([{"code": self.entity_description.key, "value": False}])

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        # If the light is currently in color mode, extract the brightness from the color data
        if self.color_mode == ColorMode.HS and (color_data := self._get_color_data()):
            return color_data.brightness

        if not self._brightness:
            return None

        brightness = self.device.status.get(self._brightness.dpcode)
        if brightness is None:
            return None

        # Remap value to our scale
        brightness = self._brightness.remap_value_to(brightness)

        # If there is a min/max value, the brightness is actually limited.
        # Meaning it is actually not on a 0-255 scale.
        if (
            self._brightness_max is not None
            and self._brightness_min is not None
            and (brightness_max := self.device.status.get(self._brightness_max.dpcode))
            is not None
            and (brightness_min := self.device.status.get(self._brightness_min.dpcode))
            is not None
        ):
            # Remap values onto our scale
            brightness_max = self._brightness_max.remap_value_to(brightness_max)
            brightness_min = self._brightness_min.remap_value_to(brightness_min)

            # Remap the brightness value from their min-max to our 0-255 scale
            brightness = remap_value(
                brightness,
                from_min=brightness_min,
                from_max=brightness_max,
            )

        return round(brightness)

    @property
    def color_temp(self) -> int | None:
        """Return the color_temp of the light."""
        if not self._color_temp:
            return None

        temperature = self.device.status.get(self._color_temp.dpcode)
        if temperature is None:
            return None

        return round(
            self._color_temp.remap_value_to(
                temperature, self.min_mireds, self.max_mireds, reverse=True
            )
        )

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hs_color of the light."""
        if self._color_data_dpcode is None or not (
            color_data := self._get_color_data()
        ):
            return None
        return color_data.hs_color

    @property
    def color_mode(self) -> ColorMode:
        """Return the color_mode of the light."""
        if self._fixed_color_mode:
            # The light supports only a single color mode, return it
            return self._fixed_color_mode

        # The light supports both color temperature and HS, determine which mode the
        # light is in. We consider it to be in HS color mode, when work mode is anything
        # else than "white".
        if (
            self._color_mode_dpcode
            and self.device.status.get(self._color_mode_dpcode) != WorkMode.WHITE
        ):
            return ColorMode.HS
        return ColorMode.COLOR_TEMP

    def _get_color_data(self) -> ColorData | None:
        """Get current color data from device."""
        if (
            self._color_data_type is None
            or self._color_data_dpcode is None
            or self._color_data_dpcode not in self.device.status
        ):
            return None

        if not (status_data := self.device.status[self._color_data_dpcode]):
            return None

        if not (status := json.loads(status_data)):
            return None

        return ColorData(
            type_data=self._color_data_type,
            h_value=status["h"],
            s_value=status["s"],
            v_value=status["v"],
        )
