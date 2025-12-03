"""Support for XT Fan."""

from __future__ import annotations
from typing import cast
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .const import TUYA_DISCOVERY_NEW, XTDeviceCategory
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaFanEntity,
    TuyaDPCodeEnumWrapper,
    TuyaDPCodeBooleanWrapper,
    TuyaFanDirectionEnumWrapper,
    TuyaFanFanSpeedEnumWrapper,
    TuyaFanFanSpeedIntegerWrapper,
    TUYA_FAN_DIRECTION_DPCODES,
    TUYA_FAN_MODE_DPCODES,
    TUYA_FAN_OSCILLATE_DPCODES,
    TUYA_FAN_SWITCH_DPCODES,
    tuya_fan_get_speed_wrapper,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)

XT_SUPPORT_TYPE = {
    XTDeviceCategory.XFJ,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up tuya fan dynamically through tuya discovery."""
    hass_data = entry.runtime_data
    this_platform = Platform.FAN

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[set[str], set[str]],
        XTEntityDescriptorManager.get_platform_descriptors(
            XT_SUPPORT_TYPE, entry.runtime_data.multi_manager, None, this_platform
        ),
    )

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered tuya fan."""
        if hass_data.manager is None:
            return
        if restrict_dpcode is not None:
            return None
        entities: list[XTFanEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if device and device.category in supported_descriptors:
                    entities.append(
                        XTFanEntity(
                            device,
                            hass_data.manager,
                            direction_wrapper=TuyaFanDirectionEnumWrapper.find_dpcode(
                                device, TUYA_FAN_DIRECTION_DPCODES, prefer_function=True
                            ),
                            mode_wrapper=TuyaDPCodeEnumWrapper.find_dpcode(
                                device, TUYA_FAN_MODE_DPCODES, prefer_function=True
                            ),
                            oscillate_wrapper=TuyaDPCodeBooleanWrapper.find_dpcode(
                                device, TUYA_FAN_OSCILLATE_DPCODES, prefer_function=True
                            ),
                            speed_wrapper=tuya_fan_get_speed_wrapper(device),
                            switch_wrapper=TuyaDPCodeBooleanWrapper.find_dpcode(
                                device, TUYA_FAN_SWITCH_DPCODES, prefer_function=True
                            ),
                        )
                    )
        async_add_entities(entities)

    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTFanEntity(XTEntity, TuyaFanEntity):
    """XT Fan Device."""

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        *,
        direction_wrapper: TuyaFanDirectionEnumWrapper | None,
        mode_wrapper: TuyaDPCodeEnumWrapper | None,
        oscillate_wrapper: TuyaDPCodeBooleanWrapper | None,
        speed_wrapper: (
            TuyaFanFanSpeedEnumWrapper | TuyaFanFanSpeedIntegerWrapper | None
        ),
        switch_wrapper: TuyaDPCodeBooleanWrapper | None,
    ) -> None:
        """Init XT Fan Device."""
        super(XTFanEntity, self).__init__(device, device_manager)
        super(XTEntity, self).__init__(
            device,
            device_manager,  # type: ignore
            direction_wrapper=direction_wrapper,
            mode_wrapper=mode_wrapper,
            oscillate_wrapper=oscillate_wrapper,
            speed_wrapper=speed_wrapper,
            switch_wrapper=switch_wrapper,
        )
        self.device = device
        self.device_manager = device_manager
