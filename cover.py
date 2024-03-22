"""Support for Tuya Cover."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityDescription,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantTuyaData
from .base import IntegerTypeData, TuyaEntity
from .const import DOMAIN, TUYA_DISCOVERY_NEW, DPCode, DPType


@dataclass(frozen=True)
class TuyaCoverEntityDescription(CoverEntityDescription):
    """Describe an Tuya cover entity."""

    current_state: DPCode | None = None
    current_state_inverse: bool = False
    current_position: DPCode | tuple[DPCode, ...] | None = None
    set_position: DPCode | None = None
    open_instruction_value: str = "open"
    close_instruction_value: str = "close"
    stop_instruction_value: str = "stop"


COVERS: dict[str, tuple[TuyaCoverEntityDescription, ...]] = {
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya cover dynamically through Tuya discovery."""
    hass_data: HomeAssistantTuyaData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered tuya cover."""
        entities: list[TuyaCoverEntity] = []
        for device_id in device_ids:
            device = hass_data.manager.device_map[device_id]
            if descriptions := COVERS.get(device.category):
                entities.extend(
                    TuyaCoverEntity(device, hass_data.manager, description)
                    for description in descriptions
                    if (
                        description.key in device.function
                        or description.key in device.status_range
                    )
                )

        async_add_entities(entities)

    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaCoverEntity(TuyaEntity, CoverEntity):
    """Tuya Cover Device."""

    _current_position: IntegerTypeData | None = None
    _set_position: IntegerTypeData | None = None
    _tilt: IntegerTypeData | None = None
    entity_description: TuyaCoverEntityDescription

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: TuyaCoverEntityDescription,
    ) -> None:
        """Init Tuya Cover."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"
        self._attr_supported_features = CoverEntityFeature(0)

        # Check if this cover is based on a switch or has controls
        if self.find_dpcode(description.key, prefer_function=True):
            if device.function[description.key].type == "Boolean":
                self._attr_supported_features |= (
                    CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
                )
            elif enum_type := self.find_dpcode(
                description.key, dptype=DPType.ENUM, prefer_function=True
            ):
                if description.open_instruction_value in enum_type.range:
                    self._attr_supported_features |= CoverEntityFeature.OPEN
                if description.close_instruction_value in enum_type.range:
                    self._attr_supported_features |= CoverEntityFeature.CLOSE
                if description.stop_instruction_value in enum_type.range:
                    self._attr_supported_features |= CoverEntityFeature.STOP

        # Determine type to use for setting the position
        if int_type := self.find_dpcode(
            description.set_position, dptype=DPType.INTEGER, prefer_function=True
        ):
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION
            self._set_position = int_type
            # Set as default, unless overwritten below
            self._current_position = int_type

        # Determine type for getting the position
        if int_type := self.find_dpcode(
            description.current_position, dptype=DPType.INTEGER, prefer_function=True
        ):
            self._current_position = int_type

        # Determine type to use for setting the tilt
        if int_type := self.find_dpcode(
            (DPCode.ANGLE_HORIZONTAL, DPCode.ANGLE_VERTICAL),
            dptype=DPType.INTEGER,
            prefer_function=True,
        ):
            self._attr_supported_features |= CoverEntityFeature.SET_TILT_POSITION
            self._tilt = int_type

    @property
    def current_cover_position(self) -> int | None:
        """Return cover current position."""
        if self._current_position is None:
            return None

        if (position := self.device.status.get(self._current_position.dpcode)) is None:
            return None

        return round(
            self._current_position.remap_value_to(position, 0, 100, reverse=True)
        )

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        if self._tilt is None:
            return None

        if (angle := self.device.status.get(self._tilt.dpcode)) is None:
            return None

        return round(self._tilt.remap_value_to(angle, 0, 100))

    @property
    def is_closed(self) -> bool | None:
        """Return true if cover is closed."""
        if (
            self.entity_description.current_state is not None
            and (
                current_state := self.device.status.get(
                    self.entity_description.current_state
                )
            )
            is not None
        ):
            return self.entity_description.current_state_inverse is not (
                current_state in (True, "fully_close")
            )

        if (position := self.current_cover_position) is not None:
            return position == 0

        return None

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        value: bool | str = True
        if self.find_dpcode(
            self.entity_description.key, dptype=DPType.ENUM, prefer_function=True
        ):
            value = self.entity_description.open_instruction_value

        commands: list[dict[str, str | int]] = [
            {"code": self.entity_description.key, "value": value}
        ]

        if self._set_position is not None:
            commands.append(
                {
                    "code": self._set_position.dpcode,
                    "value": round(
                        self._set_position.remap_value_from(100, 0, 100, reverse=True),
                    ),
                }
            )

        self._send_command(commands)

    def close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        value: bool | str = False
        if self.find_dpcode(
            self.entity_description.key, dptype=DPType.ENUM, prefer_function=True
        ):
            value = self.entity_description.close_instruction_value

        commands: list[dict[str, str | int]] = [
            {"code": self.entity_description.key, "value": value}
        ]

        if self._set_position is not None:
            commands.append(
                {
                    "code": self._set_position.dpcode,
                    "value": round(
                        self._set_position.remap_value_from(0, 0, 100, reverse=True),
                    ),
                }
            )

        self._send_command(commands)

    def set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        if self._set_position is None:
            raise RuntimeError(
                "Cannot set position, device doesn't provide methods to set it"
            )

        self._send_command(
            [
                {
                    "code": self._set_position.dpcode,
                    "value": round(
                        self._set_position.remap_value_from(
                            kwargs[ATTR_POSITION], 0, 100, reverse=True
                        )
                    ),
                }
            ]
        )

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self._send_command(
            [
                {
                    "code": self.entity_description.key,
                    "value": self.entity_description.stop_instruction_value,
                }
            ]
        )

    def set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        if self._tilt is None:
            raise RuntimeError(
                "Cannot set tilt, device doesn't provide methods to set it"
            )

        self._send_command(
            [
                {
                    "code": self._tilt.dpcode,
                    "value": round(
                        self._tilt.remap_value_from(
                            kwargs[ATTR_TILT_POSITION], 0, 100, reverse=True
                        )
                    ),
                }
            ]
        )
