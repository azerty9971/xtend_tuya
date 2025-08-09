"""Support for XT switches."""

from __future__ import annotations
from typing import Any, cast
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
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
    CROSS_CATEGORY_DEVICE_DESCRIPTOR,
    LOGGER,  # noqa: F401
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaSwitchEntity,
    TuyaSwitchEntityDescription,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)


class XTSwitchEntityDescription(TuyaSwitchEntityDescription, frozen_or_thawed=True):
    override_tuya: bool = False
    dont_send_to_cloud: bool = False
    on_value: Any = None
    off_value: Any = None

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSwitchEntityDescription,
    ) -> XTSwitchEntity:
        return XTSwitchEntity(
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
            on_value="yes",
            off_value="no",
            entity_registry_visible_default=False,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.XT_COVER_INVERT_STATUS,
            translation_key="xt_cover_invert_status",
            entity_category=EntityCategory.CONFIG,
            dont_send_to_cloud=True,
            on_value="yes",
            off_value="no",
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
            key=XTDPCode.DEODORIZATION,
            translation_key="deodorization",
            entity_category=EntityCategory.CONFIG,
            icon="mdi:bacteria",
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.FACTORY_RESET,
            translation_key="factory_reset",
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
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
            key=XTDPCode.LIGHT,
            translation_key="light",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.MANUAL_CLEAN,
            translation_key="manual_clean",
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
            key=XTDPCode.CLEANING,
            translation_key="one_click_cleanup",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.QUIET_TIMING_ON,
            translation_key="quiet_timing_on",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.REBOOT,
            translation_key="child_lock",
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
            key=XTDPCode.RFID,
            translation_key="rfid",
            entity_category=EntityCategory.CONFIG,
        ),
        XTSwitchEntityDescription(
            key=XTDPCode.IDVERIFICATIONSET,
            translation_key="id_verification_set",
            entity_category=EntityCategory.CONFIG,
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
}

# Lock duplicates
SWITCHES["videolock"] = SWITCHES["jtmspro"]
SWITCHES["jtmsbh"] = SWITCHES["jtmspro"]


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up tuya sensors dynamically through tuya discovery."""
    hass_data = entry.runtime_data

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, tuple[XTSwitchEntityDescription, ...]],
            dict[str, tuple[XTSwitchEntityDescription, ...]],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            SWITCHES, entry.runtime_data.multi_manager, Platform.SWITCH
        ),
    )

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered tuya sensor."""
        if hass_data.manager is None:
            return
        entities: list[XTSwitchEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if category_descriptions := XTEntityDescriptorManager.get_category_descriptors(supported_descriptors, device.category):
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
                            description, device, hass_data.manager
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device, description, True, externally_managed_dpcodes
                        )
                    )
                    entities.extend(
                        XTSwitchEntity.get_entity_instance(
                            description, device, hass_data.manager
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device, description, False, externally_managed_dpcodes
                        )
                    )

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors(
        Platform.SWITCH, supported_descriptors
    )
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
    ) -> None:
        """Init TuyaHaSwitch."""
        super(XTSwitchEntity, self).__init__(device, device_manager, description)
        super(XTEntity, self).__init__(device, device_manager, description)  # type: ignore
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description  # type: ignore

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        current_value = self.device.status.get(self.entity_description.key, False)
        if (
            self.entity_description.on_value is not None
            and self.entity_description.off_value is not None
        ):
            if self.entity_description.on_value == current_value:
                return True
            if self.entity_description.off_value == current_value:
                return False
        elif self.entity_description.on_value is not None:
            if self.entity_description.on_value == current_value:
                return True
            else:
                return False
        elif self.entity_description.off_value is not None:
            if self.entity_description.off_value == current_value:
                return False
            else:
                return True

        return super().is_on

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        if self.entity_description.dont_send_to_cloud:
            if self.entity_description.on_value is not None:
                self.device.status[self.entity_description.key] = (
                    self.entity_description.on_value
                )
            else:
                self.device.status[self.entity_description.key] = True
            self.device_manager.multi_device_listener.update_device(
                self.device, [self.entity_description.key]
            )
        else:
            super().turn_on(**kwargs)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        if self.entity_description.dont_send_to_cloud:
            if self.entity_description.off_value is not None:
                self.device.status[self.entity_description.key] = (
                    self.entity_description.off_value
                )
            else:
                self.device.status[self.entity_description.key] = False
            self.device_manager.multi_device_listener.update_device(
                self.device, [self.entity_description.key]
            )
        else:
            super().turn_off(**kwargs)

    @staticmethod
    def get_entity_instance(
        description: XTSwitchEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
    ) -> XTSwitchEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(device, device_manager, description)
        return XTSwitchEntity(
            device, device_manager, XTSwitchEntityDescription(**description.__dict__)
        )
