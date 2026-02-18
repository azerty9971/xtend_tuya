"""Support for XT switches."""

from __future__ import annotations
from typing import cast, Any
from dataclasses import dataclass
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
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
    CROSS_CATEGORY_DEVICE_DESCRIPTOR,
    XTMultiManagerPostSetupCallbackPriority,
    LOGGER,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaSwitchEntity,
    TuyaSwitchEntityDescription,
    TuyaDPCodeBooleanWrapper,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)
from .smart_cover_control import SmartCoverManager


@dataclass(frozen=True)
class XTSwitchEntityDescription(TuyaSwitchEntityDescription, frozen_or_thawed=True):
    override_tuya: bool = False
    dont_send_to_cloud: bool = False

    # duplicate the entity if handled by another integration
    ignore_other_dp_code_handler: bool = False

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSwitchEntityDescription,
        dpcode_wrapper: TuyaDPCodeBooleanWrapper,
    ) -> XTSwitchEntity:
        return XTSwitchEntity(
            device=device,
            device_manager=device_manager,
            description=XTSwitchEntityDescription(**description.__dict__),
            dpcode_wrapper=dpcode_wrapper,
        )


@dataclass
class XTSmartCoverSwitchEntityDescription(SwitchEntityDescription):
    """Describe a Smart Cover Switch entity."""

    control_dp: str | None = None
    force_update: bool = False
    entity_registry_enabled_default: bool = True
    entity_registry_visible_default: bool = True

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSmartCoverSwitchEntityDescription,
    ) -> XTSmartCoverSwitchEntity:
        return XTSmartCoverSwitchEntity(
            device=device, device_manager=device_manager, description=description
        )


# All descriptions can be found here. Mostly the Boolean data types in the
# default instruction set of each category end up being a Switch.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
SWITCHES: dict[str, tuple[XTSwitchEntityDescription, ...]] = {
    CROSS_CATEGORY_DEVICE_DESCRIPTOR: (
        XTSwitchEntityDescription(
            key=XTDPCode.XT_COVER_INVERT_CONTROL,
            translation_key="xt_cover_invert_control",
            entity_category=EntityCategory.CONFIG,
            dont_send_to_cloud=True,
            entity_registry_visible_default=False,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.XT_COVER_INVERT_STATUS,
            translation_key="xt_cover_invert_status",
            entity_category=EntityCategory.CONFIG,
            dont_send_to_cloud=True,
            entity_registry_visible_default=False,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.SWITCH,
            translation_key="switch",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.SWITCH_1,
            translation_key="switch_1",
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.SWITCH_2,
            translation_key="switch_2",
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.SWITCH_3,
            translation_key="switch_3",
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.SWITCH_4,
            translation_key="switch_4",
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.SWITCH_5,
            translation_key="switch_5",
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.SWITCH_6,
            translation_key="switch_6",
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.SWITCH_7,
            translation_key="switch_7",
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.SWITCH_8,
            translation_key="switch_8",
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.WEATHER_SWITCH,
            translation_key="weather_switch",
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.SWITCH_ENABLED,
            translation_key="switch_enabled",
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.SWITCH_PIR,
            translation_key="switch_pir",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.SWITCH_ON,
            translation_key="switch",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:human-child",
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.POWERONOFF,
            translation_key="power",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.POWERON,
            translation_key="power",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "cwwsq": (
        XTSwitchEntityDescription(
            key=XTDPCode.KEY_REC,
            translation_key="key_rec",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "dbl": (
        XTSwitchEntityDescription(
            key=XTDPCode.SOUND,
            translation_key="sound",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "ggq": (
        XTSwitchEntityDescription(
            key=XTDPCode.CONTROL_SKIP,
            translation_key="control_skip",
        ),
    ),
    "gyd": (),
    "hps": (
        XTSwitchEntityDescription(
            key=XTDPCode.INDICATOR_LED,
            translation_key="indicator_light",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "jtmspro": (
        XTSwitchEntityDescription(
            key=XTDPCode.AUTOMATIC_LOCK,
            translation_key="automatic_lock",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.ALARM_SWITCH,
            translation_key="alarm_switch",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
        ),
    ),
    "mk": (
        XTSwitchEntityDescription(
            key=XTDPCode.AUTOMATIC_LOCK,
            translation_key="automatic_lock",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.PHOTO_AGAIN,
            translation_key="photo_again",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
        ),
    ),
    "MPPT": (),
    # Automatic cat litter box
    # Note: Undocumented
    "msp": (
        XTSwitchEntityDescription(
            key=XTDPCode.AUTO_CLEAN,
            translation_key="auto_clean",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:bacteria",
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.AUTO_DEORDRIZER,
            translation_key="auto_deordrizer",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.BEEP,
            translation_key="beep",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.CALIBRATION,
            translation_key="calibration",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.CHILD_LOCK,
            translation_key="child_lock",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:human-child",
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.CLEAN_NOTICE,
            translation_key="clean_notice",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.CLEAN_TASTE_SWITCH,
            translation_key="clean_tasteswitch",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.CLEAN_TIME_SWITCH,
            translation_key="clean_time_switch",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.CLEANING,
            translation_key="one_click_cleanup",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.DEEP_CLEAN,
            translation_key="deep_clean",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.DEODORIZATION,
            translation_key="deodorization",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:bacteria",
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.INDICATOR_LIGHT,
            translation_key="indicator_light",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.INDUCTION_CLEAN,
            translation_key="induction_clean",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.INFRARED_SENSOR_SWITCH,
            translation_key="infrared_sensor_switch",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.NET_NOTICE,
            translation_key="net_notice",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.NOT_DISTURB_SWITCH,
            translation_key="not_disturb_switch",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.ODOURLESS,
            translation_key="odourless",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.QUIET_TIMING_ON,
            translation_key="quiet_timing_on",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.REBOOT,
            translation_key="reboot",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.SLEEP,
            translation_key="sleep",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.SLEEPING,
            translation_key="sleeping",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.SMART_CLEAN,
            translation_key="smart_clean",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.START,
            translation_key="start",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:bacteria",
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.STORE_FULL_NOTIFY,
            translation_key="store_full_notify",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.THIN_FECES,
            translation_key="thin_feces",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.TOILET_NOTICE,
            translation_key="toilet_notice",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:toilet",
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.UNIT,
            translation_key="unit",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.UV,
            translation_key="uv",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "mzj": (),
    "qccdz": (
        XTSwitchEntityDescription(
            key=XTDPCode.IDVERIFICATIONSET,
            translation_key="id_verification_set",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.RFID,
            translation_key="rfid",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    # QT-08W Solar Intelligent Water Valve
    "sfkzq": (
        XTSwitchEntityDescription(
            key=XTDPCode.SWITCH,
            translation_key="valve",
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.WORK_MODE,
            translation_key="sleep_mode",
        ),
    ),
    "wk": (),
    "wnykq": (),
    "xfj": (
        XTSwitchEntityDescription(
            key=XTDPCode.UV_LIGHT,
            translation_key="uv_light",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.ANION,
            translation_key="anion",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "ywcgq": (
        XTSwitchEntityDescription(
            key=XTDPCode.AUTO_PUMP,
            translation_key="pump_auto",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.PUMP_MODE,
            translation_key="pump_mode",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.RELAY_SWITCH_1,
            translation_key="pump_switch",
        ),
    ),
    # Smart Cover positioning switches
    "cl": (
        XTSmartCoverSwitchEntityDescription(
            key="smart_cover_positioning_enabled_1",
            translation_key="smart_cover_positioning_enabled",
            name="Enable Custom Calibration",
            icon="mdi:cog",
            entity_category=EntityCategory.CONFIG,
            control_dp=XTDPCode.CONTROL,
        ),
        XTSmartCoverSwitchEntityDescription(
            key="smart_cover_positioning_enabled_2",
            translation_key="smart_cover_positioning_enabled_2",
            name="Enable Custom Calibration 2",
            icon="mdi:cog",
            entity_category=EntityCategory.CONFIG,
            control_dp=XTDPCode.CONTROL_2,
        ),
        XTSmartCoverSwitchEntityDescription(
            key="smart_cover_positioning_enabled_3",
            translation_key="smart_cover_positioning_enabled_3",
            name="Enable Custom Calibration 3",
            icon="mdi:cog",
            entity_category=EntityCategory.CONFIG,
            control_dp=XTDPCode.CONTROL_3,
        ),
    ),
    "clkg": (
        XTSmartCoverSwitchEntityDescription(
            key="smart_cover_positioning_enabled_1",
            translation_key="smart_cover_positioning_enabled",
            name="Enable Custom Calibration",
            icon="mdi:cog",
            entity_category=EntityCategory.CONFIG,
            control_dp=XTDPCode.CONTROL,
        ),
        XTSmartCoverSwitchEntityDescription(
            key="smart_cover_positioning_enabled_2",
            translation_key="smart_cover_positioning_enabled_2",
            name="Enable Custom Calibration 2",
            icon="mdi:cog",
            entity_category=EntityCategory.CONFIG,
            control_dp=XTDPCode.CONTROL_2,
        ),
        XTSmartCoverSwitchEntityDescription(
            key="smart_cover_positioning_enabled_3",
            translation_key="smart_cover_positioning_enabled_3",
            name="Enable Custom Calibration 3",
            icon="mdi:cog",
            entity_category=EntityCategory.CONFIG,
            control_dp=XTDPCode.CONTROL_3,
        ),
    ),
}

# Lock duplicates
SWITCHES["videolock"] = SWITCHES["jtmspro"]
SWITCHES["jtmsbh"] = SWITCHES["jtmspro"]


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up tuya sensors dynamically through tuya discovery."""
    hass_data = entry.runtime_data
    this_platform = Platform.SWITCH

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    # Initialize smart cover manager if not exists
    if not hasattr(hass_data.manager, 'smart_cover_manager'):
        hass_data.manager.smart_cover_manager = SmartCoverManager(hass)

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, tuple[XTSwitchEntityDescription, ...]],
            dict[str, tuple[XTSwitchEntityDescription, ...]],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            SWITCHES,
            entry.runtime_data.multi_manager,
            XTSwitchEntityDescription,
            this_platform,
        ),
    )

    @callback
    def async_add_generic_entities(device_map) -> None:
        if hass_data.manager is None:
            return
        entities: list[XTSwitchEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                generic_dpcodes = XTEntity.get_generic_dpcodes_for_this_platform(
                    device, this_platform
                )
                for dpcode in generic_dpcodes:
                    descriptor = XTSwitchEntityDescription(
                        key=dpcode,
                        translation_key="xt_generic_switch",
                        translation_placeholders={
                            "name": XTEntity.get_human_name(dpcode)
                        },
                        entity_registry_enabled_default=False,
                        entity_registry_visible_default=False,
                    )
                    if dpcode_wrapper := TuyaDPCodeBooleanWrapper.find_dpcode(
                        device, descriptor.key, prefer_function=True
                    ):
                        entities.append(
                            XTSwitchEntity.get_entity_instance(
                                descriptor, device, hass_data.manager, dpcode_wrapper
                            )
                        )
        async_add_entities(entities)

    created_smart_cover_ids: set[str] = set()

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered tuya sensor."""
        if hass_data.manager is None:
            return
        entities: list[XTSwitchEntity | XTSmartCoverSwitchEntity] = []
        device_ids = [*device_map]
        # Handle smart cover switch entities for cl/clkg devices
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if device.category in ["cl", "clkg"]:
                    smart_cover_descs = SWITCHES.get(device.category)
                    if smart_cover_descs:
                        for desc in smart_cover_descs:
                            if isinstance(desc, XTSmartCoverSwitchEntityDescription):
                                # Compare as string to handle enum vs string keys
                                dp_str = desc.control_dp.value if hasattr(desc.control_dp, 'value') else str(desc.control_dp)
                                dp_in_range = any(
                                    (k.value if hasattr(k, 'value') else str(k)) == dp_str
                                    for k in device.status_range
                                )
                                dp_in_func = any(
                                    (k.value if hasattr(k, 'value') else str(k)) == dp_str
                                    for k in device.function
                                ) if hasattr(device, 'function') else False
                                if desc.control_dp and (dp_in_range or dp_in_func):
                                    entity_uid = f"{device.id}_{dp_str}_{desc.key}"
                                    if entity_uid not in created_smart_cover_ids:
                                        created_smart_cover_ids.add(entity_uid)
                                        entities.append(
                                            XTSmartCoverSwitchEntity.get_entity_instance(
                                                desc, device, hass_data.manager
                                            )
                                        )
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if category_descriptions := XTEntityDescriptorManager.get_category_descriptors(
                    supported_descriptors, device.category
                ):
                    externally_managed_dpcodes = (
                        XTEntityDescriptorManager.get_category_keys(
                            externally_managed_descriptors.get(device.category)
                        )
                    )
                    if restrict_dpcode is not None:
                        category_descriptions = cast(
                            tuple[XTSwitchEntityDescription, ...],
                            restrict_descriptor_category(
                                category_descriptions, [restrict_dpcode]
                            ),
                        )
                    entities.extend(
                        XTSwitchEntity.get_entity_instance(
                            description, device, hass_data.manager, dpcode_wrapper
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
                                dpcode_wrapper := TuyaDPCodeBooleanWrapper.find_dpcode(
                                    device, description.key, prefer_function=True
                                )
                            )
                        )
                    )
                    entities.extend(
                        XTSwitchEntity.get_entity_instance(
                            description, device, hass_data.manager, dpcode_wrapper
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
                                dpcode_wrapper := TuyaDPCodeBooleanWrapper.find_dpcode(
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


class XTSwitchEntity(XTEntity, TuyaSwitchEntity):
    """XT Switch Device."""

    entity_description: XTSwitchEntityDescription

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSwitchEntityDescription,
        dpcode_wrapper: TuyaDPCodeBooleanWrapper,
    ) -> None:
        """Init TuyaHaSwitch."""
        super(XTSwitchEntity, self).__init__(
            device, device_manager, description, dpcode_wrapper=dpcode_wrapper
        )
        super(XTEntity, self).__init__(
            device,
            device_manager,  # type: ignore
            description,
            dpcode_wrapper,
        )
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description  # type: ignore

    async def async_turn_on(self, **kwargs: Any) -> None:
        if self.entity_description.dont_send_to_cloud:
            if self.entity_description.key in self.device.status:
                self.device.status[self.entity_description.key] = True
                self.device_manager.multi_device_listener.update_device(self.device, [self.entity_description.key])
            return
        await super().async_turn_on(**kwargs)
    
    async def async_turn_off(self, **kwargs: Any) -> None:
        if self.entity_description.dont_send_to_cloud:
            if self.entity_description.key in self.device.status:
                self.device.status[self.entity_description.key] = False
                self.device_manager.multi_device_listener.update_device(self.device, [self.entity_description.key])
            return
        await super().async_turn_off(**kwargs)

    @staticmethod
    def get_entity_instance(
        description: XTSwitchEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
        dpcode_wrapper: TuyaDPCodeBooleanWrapper,
    ) -> XTSwitchEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(
                device, device_manager, description, dpcode_wrapper
            )
        return XTSwitchEntity(
            device,
            device_manager,
            XTSwitchEntityDescription(**description.__dict__),
            dpcode_wrapper,
        )


class XTSmartCoverSwitchEntity(XTEntity, RestoreEntity, SwitchEntity):
    """XT Smart Cover Switch Entity for enabling/disabling smart positioning."""

    entity_description: XTSmartCoverSwitchEntityDescription

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSmartCoverSwitchEntityDescription,
    ) -> None:
        """Initialize the switch entity."""
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description

        base_name = "Enable Custom Calibration"
        if description.control_dp == XTDPCode.CONTROL_2:
            base_name = "Enable Custom Calibration 2"
        elif description.control_dp == XTDPCode.CONTROL_3:
            base_name = "Enable Custom Calibration 3"

        self.entity_description.name = base_name
        super().__init__(device, device_manager, description)
        self._attr_is_on = False

    @property
    def unique_id(self) -> str:
        """Return unique ID for the entity."""
        return f"{self.device.id}_{self.entity_description.control_dp}_{self.entity_description.key}"

    @property
    def is_on(self) -> bool:
        """Return if smart positioning is enabled."""
        return self._attr_is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable smart positioning."""
        self._attr_is_on = True

        if hasattr(self.device_manager, 'smart_cover_manager'):
            controller = self.device_manager.smart_cover_manager.get_controller(
                self.device.id, self.entity_description.control_dp
            )
            if not controller:
                cover_entity_id = f"cover.{self.device.name.lower().replace(' ', '_')}"
                try:
                    controller = await self.device_manager.smart_cover_manager.get_or_create_controller(
                        self.device,
                        self.device_manager,
                        cover_entity_id,
                        self.entity_description.control_dp,
                    )
                except Exception:
                    controller = None
            if controller:
                controller.positioning_enabled = True
                await controller._save_state()

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable smart positioning."""
        self._attr_is_on = False

        if hasattr(self.device_manager, 'smart_cover_manager'):
            controller = self.device_manager.smart_cover_manager.get_controller(
                self.device.id, self.entity_description.control_dp
            )
            if controller:
                controller.positioning_enabled = False
                await controller._save_state()

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Entity added to hass."""
        await super().async_added_to_hass()

        # Read positioning_enabled directly from storage file.
        # This avoids timing issues - controllers may not exist yet because
        # cover entities create them in post_setup_callbacks which run AFTER
        # all platform entities' async_added_to_hass.
        control_dp_str = str(self.entity_description.control_dp)
        store_key = f"xtend_tuya_smart_cover_{self.device.id}_{control_dp_str}"
        try:
            from homeassistant.helpers.storage import Store
            store = Store(self.hass, 1, store_key)
            stored_data = await store.async_load()
            if stored_data and isinstance(stored_data, dict):
                self._attr_is_on = stored_data.get("positioning_enabled", False)
            else:
                # No storage data yet - fall back to HA restore state
                last_state = await self.async_get_last_state()
                if last_state is not None and last_state.state not in ("unknown", "unavailable"):
                    self._attr_is_on = last_state.state.lower() == "on"
        except Exception as e:
            LOGGER.warning(f"{self.device.name}: Failed to load positioning state from storage: {e}")
            last_state = await self.async_get_last_state()
            if last_state is not None and last_state.state not in ("unknown", "unavailable"):
                self._attr_is_on = last_state.state.lower() == "on"

        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        dp_str = self.entity_description.control_dp.value if hasattr(self.entity_description.control_dp, 'value') else str(self.entity_description.control_dp)
        in_range = any((k.value if hasattr(k, 'value') else str(k)) == dp_str for k in self.device.status_range)
        in_func = any((k.value if hasattr(k, 'value') else str(k)) == dp_str for k in self.device.function) if hasattr(self.device, 'function') else False
        return in_range or in_func

    @staticmethod
    def get_entity_instance(
        description: XTSmartCoverSwitchEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
    ) -> XTSmartCoverSwitchEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(device, device_manager, description)
        return XTSmartCoverSwitchEntity(device, device_manager, description)
