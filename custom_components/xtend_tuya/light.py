"""Support for the XT lights."""

from __future__ import annotations
from typing import cast
import json
from dataclasses import dataclass
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.light import (
    ATTR_HS_COLOR,
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
)
from homeassistant.util.color import color_temperature_kelvin_to_mired
from .multi_manager.shared.threading import XTEventLoopProtector
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .util import (
    restrict_descriptor_category,
)
from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .const import (
    TUYA_DISCOVERY_NEW,
    XTDPCode,
    XTMultiManagerPostSetupCallbackPriority,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaLightEntity,
    TuyaLightEntityDescription,
    TuyaDPCode,
    TuyaDPCodeEnumWrapper,
    TuyaDPCodeBooleanWrapper,
    TuyaLightBrightnessWrapper,
    TuyaLightColorDataWrapper,
    TuyaLightColorTempWrapper,
    tuya_light_get_brightness_wrapper,
    tuya_light_get_color_data_wrapper,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)


@dataclass(frozen=True)
class XTLightEntityDescription(TuyaLightEntityDescription):
    """Describe an Tuya light entity."""

    brightness_max: TuyaDPCode | XTDPCode | None = None  # type: ignore
    brightness_min: TuyaDPCode | XTDPCode | None = None  # type: ignore
    brightness: (  # type: ignore
        TuyaDPCode | tuple[TuyaDPCode, ...] | XTDPCode | tuple[XTDPCode, ...] | None
    ) = None
    color_data: (  # type: ignore
        TuyaDPCode | tuple[TuyaDPCode, ...] | XTDPCode | tuple[XTDPCode, ...] | None
    ) = None
    color_mode: TuyaDPCode | XTDPCode | None = None  # type: ignore
    color_temp: (  # type: ignore
        TuyaDPCode | tuple[TuyaDPCode, ...] | XTDPCode | tuple[XTDPCode, ...] | None
    ) = None

    # duplicate the entity if handled by another integration
    ignore_other_dp_code_handler: bool = False

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTLightEntityDescription,
        *,
        brightness_wrapper: TuyaLightBrightnessWrapper | None,
        color_data_wrapper: TuyaLightColorDataWrapper | None,
        color_mode_wrapper: TuyaDPCodeEnumWrapper | None,
        color_temp_wrapper: TuyaLightColorTempWrapper | None,
        switch_wrapper: TuyaDPCodeBooleanWrapper,
    ) -> XTLightEntity:
        return XTLightEntity(
            device=device,
            device_manager=device_manager,
            description=XTLightEntityDescription(**description.__dict__),
            brightness_wrapper=brightness_wrapper,
            color_data_wrapper=color_data_wrapper,
            color_mode_wrapper=color_mode_wrapper,
            color_temp_wrapper=color_temp_wrapper,
            switch_wrapper=switch_wrapper,
        )


LIGHTS: dict[str, tuple[XTLightEntityDescription, ...]] = {
    "dbl": (
        XTLightEntityDescription(
            key=XTDPCode.LIGHT,
            translation_key="light",
            brightness=XTDPCode.BRIGHT_VALUE,
        ),
    ),
    "msp": (
        XTLightEntityDescription(
            key=XTDPCode.LIGHT,
            translation_key="light",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "dj": (
        XTLightEntityDescription(
            key="switch",
            translation_key="light",
            brightness=("brightness_control",),
            color_temp=("color_temp_control",),
            color_data=("control_data", "hs_color_set"),
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up tuya light dynamically through tuya discovery."""
    hass_data = entry.runtime_data
    this_platform = Platform.LIGHT

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, tuple[XTLightEntityDescription, ...]],
            dict[str, tuple[XTLightEntityDescription, ...]],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            LIGHTS,
            entry.runtime_data.multi_manager,
            XTLightEntityDescription,
            this_platform,
        ),
    )

    @callback
    def async_add_generic_entities(device_map) -> None:
        if hass_data.manager is None:
            return
        entities: list[XTLightEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                generic_dpcodes = XTEntity.get_generic_dpcodes_for_this_platform(
                    device, this_platform
                )
                for dpcode in generic_dpcodes:
                    descriptor = XTLightEntityDescription(
                        key=dpcode,
                        translation_key="xt_generic_light",
                        translation_placeholders={
                            "name": XTEntity.get_human_name(dpcode)
                        },
                        entity_registry_enabled_default=False,
                        entity_registry_visible_default=False,
                    )
                    if switch_wrapper := TuyaDPCodeBooleanWrapper.find_dpcode(
                        device, descriptor.key, prefer_function=True
                    ):
                        entities.append(
                            XTLightEntity.get_entity_instance(
                                descriptor,
                                device,
                                hass_data.manager,
                                brightness_wrapper=(
                                    brightness_wrapper
                                    := tuya_light_get_brightness_wrapper(
                                        device, descriptor
                                    )
                                ),
                                color_data_wrapper=tuya_light_get_color_data_wrapper(
                                    device, descriptor, brightness_wrapper
                                ),
                                color_mode_wrapper=TuyaDPCodeEnumWrapper.find_dpcode(
                                    device, descriptor.color_mode, prefer_function=True
                                ),
                                color_temp_wrapper=TuyaLightColorTempWrapper.find_dpcode(
                                    device,
                                    descriptor.color_temp,
                                    prefer_function=True,  # type: ignore
                                ),
                                switch_wrapper=switch_wrapper,
                            )
                        )
        async_add_entities(entities)

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered tuya light."""
        if hass_data.manager is None:
            return
        entities: list[XTLightEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if (
                    category_descriptions
                    := XTEntityDescriptorManager.get_category_descriptors(
                        supported_descriptors, device.category
                    )
                ):
                    externally_managed_dpcodes = (
                        XTEntityDescriptorManager.get_category_keys(
                            externally_managed_descriptors.get(device.category)
                        )
                    )
                    if restrict_dpcode is not None:
                        category_descriptions = cast(
                            tuple[XTLightEntityDescription, ...],
                            restrict_descriptor_category(
                                category_descriptions, [restrict_dpcode]
                            ),
                        )
                    entities.extend(
                        XTLightEntity.get_entity_instance(
                            description,
                            device,
                            hass_data.manager,
                            brightness_wrapper=(
                                brightness_wrapper := tuya_light_get_brightness_wrapper(
                                    device, description
                                )
                            ),
                            color_data_wrapper=tuya_light_get_color_data_wrapper(
                                device, description, brightness_wrapper
                            ),
                            color_mode_wrapper=TuyaDPCodeEnumWrapper.find_dpcode(
                                device, description.color_mode, prefer_function=True
                            ),
                            color_temp_wrapper=TuyaLightColorTempWrapper.find_dpcode(
                                device,
                                description.color_temp,
                                prefer_function=True,  # type: ignore
                            ),
                            switch_wrapper=switch_wrapper,
                        )
                        for description in category_descriptions
                        if (
                            XTEntity.supports_description(
                                device,
                                this_platform,
                                description,
                                True,
                                externally_managed_dpcodes,
                            )
                            and (
                                switch_wrapper := TuyaDPCodeBooleanWrapper.find_dpcode(
                                    device, description.key, prefer_function=True
                                )
                            )
                        )
                    )
                    entities.extend(
                        XTLightEntity.get_entity_instance(
                            description,
                            device,
                            hass_data.manager,
                            brightness_wrapper=(
                                brightness_wrapper := tuya_light_get_brightness_wrapper(
                                    device, description
                                )
                            ),
                            color_data_wrapper=tuya_light_get_color_data_wrapper(
                                device, description, brightness_wrapper
                            ),
                            color_mode_wrapper=TuyaDPCodeEnumWrapper.find_dpcode(
                                device, description.color_mode, prefer_function=True
                            ),
                            color_temp_wrapper=TuyaLightColorTempWrapper.find_dpcode(
                                device,
                                description.color_temp,
                                prefer_function=True,  # type: ignore
                            ),
                            switch_wrapper=switch_wrapper,
                        )
                        for description in category_descriptions
                        if (
                            XTEntity.supports_description(
                                device,
                                this_platform,
                                description,
                                False,
                                externally_managed_dpcodes,
                            )
                            and (
                                switch_wrapper := TuyaDPCodeBooleanWrapper.find_dpcode(
                                    device, description.key, prefer_function=True
                                )
                            )
                        )
                    )

        async_add_entities(entities)
        if restrict_dpcode is None:
            hass_data.manager.add_post_setup_callback(
                XTMultiManagerPostSetupCallbackPriority.PRIORITY_LAST,
                async_add_generic_entities,
                device_map,
            )

    hass_data.manager.register_device_descriptors(this_platform, supported_descriptors)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTLightEntity(XTEntity, TuyaLightEntity):
    """XT light device."""

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTLightEntityDescription,
        *,
        brightness_wrapper: TuyaLightBrightnessWrapper | None,
        color_data_wrapper: TuyaLightColorDataWrapper | None,
        color_mode_wrapper: TuyaDPCodeEnumWrapper | None,
        color_temp_wrapper: TuyaLightColorTempWrapper | None,
        switch_wrapper: TuyaDPCodeBooleanWrapper,
    ) -> None:
        super(XTLightEntity, self).__init__(device, device_manager, description)
        super(XTEntity, self).__init__(
            device,
            device_manager,  # type: ignore
            description,
            brightness_wrapper=brightness_wrapper,
            color_data_wrapper=color_data_wrapper,
            color_mode_wrapper=color_mode_wrapper,
            color_temp_wrapper=color_temp_wrapper,
            switch_wrapper=switch_wrapper,
        )
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description

    async def async_turn_on(self, **kwargs):
        if self.device.category == "dj":
            cmds: list[dict] = []
            cmds.append({"code": "switch", "value": True})

            if ATTR_BRIGHTNESS in kwargs:
                bri = max(1, min(254, int(kwargs[ATTR_BRIGHTNESS])))
                cmds.append({"code": "brightness_control", "value": bri})

            if ATTR_COLOR_TEMP_KELVIN in kwargs:
                mired = int(
                    round(color_temperature_kelvin_to_mired(kwargs[ATTR_COLOR_TEMP_KELVIN]))
                )
                ct = max(153, min(370, mired))
                cmds.append({"code": "color_temp_control", "value": ct})
                self._attr_color_mode = ColorMode.COLOR_TEMP
                self._attr_color_temp_kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]

            if ATTR_HS_COLOR in kwargs:
                h, s_pct = kwargs[ATTR_HS_COLOR]
                v = kwargs.get(ATTR_BRIGHTNESS, getattr(self, "brightness", 255) or 255)
                h_i = int(round(h))
                s_i = int(round(s_pct * 255 / 100))
                v_i = int(round(max(0, min(255, v))))
                bri_for_color = max(1, min(254, v_i))
                cmds.append({"code": "brightness_control", "value": bri_for_color})
                h_byte = int(round((h_i % 360) * 255 / 360))
                hs_hex = f"{h_byte:02x}{s_i:02x}"
                cmds.append({"code": "hs_color_set", "value": hs_hex})
                cmds.append(
                    {
                        "code": "control_data",
                        "value": json.dumps({"h": h_i, "s": s_i, "v": v_i}),
                    }
                )
                self._attr_color_mode = ColorMode.HS
                self._attr_hs_color = (float(h), float(s_pct))
                self._attr_brightness = int(v)

            if len(cmds) == 1:
                return await super().async_turn_on(**kwargs)

            await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                self.device_manager.send_commands, self.device.id, cmds
            )
            self.async_write_ha_state()
            return

        return await super().async_turn_on(**kwargs)

    @staticmethod
    def get_entity_instance(
        description: XTLightEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
        *,
        brightness_wrapper: TuyaLightBrightnessWrapper | None,
        color_data_wrapper: TuyaLightColorDataWrapper | None,
        color_mode_wrapper: TuyaDPCodeEnumWrapper | None,
        color_temp_wrapper: TuyaLightColorTempWrapper | None,
        switch_wrapper: TuyaDPCodeBooleanWrapper,
    ) -> XTLightEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(
                device,
                device_manager,
                description,
                brightness_wrapper=brightness_wrapper,
                color_data_wrapper=color_data_wrapper,
                color_mode_wrapper=color_mode_wrapper,
                color_temp_wrapper=color_temp_wrapper,
                switch_wrapper=switch_wrapper,
            )
        return XTLightEntity(
            device,
            device_manager,
            XTLightEntityDescription(**description.__dict__),
            brightness_wrapper=brightness_wrapper,
            color_data_wrapper=color_data_wrapper,
            color_mode_wrapper=color_mode_wrapper,
            color_temp_wrapper=color_temp_wrapper,
            switch_wrapper=switch_wrapper,
        )
