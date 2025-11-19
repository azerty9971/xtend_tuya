"""Support for XT binary sensors."""

from __future__ import annotations
from dataclasses import dataclass
from typing import cast, Callable
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
)
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.json import json_loads

# from homeassistant.helpers.typing import UndefinedType
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
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaBinarySensorEntity,
    TuyaBinarySensorEntityDescription,
    TuyaDPType,
    # get_bitmap_bit_mask_tuya_binary_sensor,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)

COMPOUND_KEY: list[str] = ["key", "subkey"]


@dataclass(frozen=True)
class XTBinarySensorEntityDescription(TuyaBinarySensorEntityDescription):
    """Describes an XT binary sensor."""

    device_online: bool = False  # This DPCode represent the online status of a device
    subkey: str | None = (
        None  # Subkey to create multiple entities with the same key/dpcode
    )
    is_on: Callable | None = None  # Custom is_on function

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTBinarySensorEntityDescription,
    ) -> XTBinarySensorEntity:
        return XTBinarySensorEntity(
            device=device,
            device_manager=device_manager,
            description=XTBinarySensorEntityDescription(**description.__dict__),
        )


# Commonly used sensors
TAMPER_BINARY_SENSOR: tuple[XTBinarySensorEntityDescription, ...] = (
    XTBinarySensorEntityDescription(
        key=XTDPCode.TEMPER_ALARM,
        name="Tamper",
        device_class=BinarySensorDeviceClass.TAMPER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

PROXIMITY_BINARY_SENSOR: tuple[XTBinarySensorEntityDescription, ...] = (
    XTBinarySensorEntityDescription(
        key=XTDPCode.PRESENCE_STATE,
        translation_key="pir_state",
        device_class=BinarySensorDeviceClass.MOTION,
        on_value="presence",
    ),
    XTBinarySensorEntityDescription(
        key=XTDPCode.PIR_STATE,
        translation_key="pir_state",
        device_class=BinarySensorDeviceClass.MOTION,
        on_value="pir",
    ),
    XTBinarySensorEntityDescription(
        key=XTDPCode.PIR2,
        translation_key="pir_state",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
)

CONTACT_BINARY_SENSOR: tuple[XTBinarySensorEntityDescription, ...] = (
    XTBinarySensorEntityDescription(
        key=XTDPCode.DOORCONTACT_STATE,
        translation_key="door_contact_state",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_registry_enabled_default=True,
    ),
    XTBinarySensorEntityDescription(
        key=XTDPCode.DOORCONTACT_STATE_2,
        translation_key="door_contact_state_2",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_registry_enabled_default=True,
    ),
    XTBinarySensorEntityDescription(
        key=XTDPCode.DOORCONTACT_STATE_3,
        translation_key="door_contact_state_3",
        device_class=BinarySensorDeviceClass.DOOR,
        entity_registry_enabled_default=True,
    ),
)

# All descriptions can be found here. Mostly the Boolean data types in the
# default status set of each category (that don't have a set instruction)
# end up being a binary sensor.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
BINARY_SENSORS: dict[str, tuple[XTBinarySensorEntityDescription, ...]] = {
    CROSS_CATEGORY_DEVICE_DESCRIPTOR: (
        *PROXIMITY_BINARY_SENSOR,
        *TAMPER_BINARY_SENSOR,
        *CONTACT_BINARY_SENSOR,
    ),
    "jtmspro": (
        XTBinarySensorEntityDescription(
            key=XTDPCode.LOCK_MOTOR_STATE,
            translation_key="lock_motor_state",
            device_class=BinarySensorDeviceClass.LOCK,
            on_value=True,
        ),
    ),
    "msp": (
        # If 1 is reported, it will be counted once.
        # If 0 is reported, it will not be counted
        # (today and the average number of toilet visits will be counted on the APP)
        XTBinarySensorEntityDescription(
            key=XTDPCode.CLEANING_NUM,
            translation_key="cleaning_num",
        ),
        XTBinarySensorEntityDescription(
            key=XTDPCode.MONITORING,
            device_class=BinarySensorDeviceClass.OCCUPANCY,
            entity_category=EntityCategory.DIAGNOSTIC,
            translation_key="litter_occupied",
            entity_registry_enabled_default=False,
        ),
        XTBinarySensorEntityDescription(
            key=XTDPCode.POWER,
            translation_key="power",
            entity_registry_enabled_default=False,
        ),
        XTBinarySensorEntityDescription(
            key=XTDPCode.STORE_FULL_NOTIFY,
            translation_key="store_full_notify",
            entity_registry_enabled_default=True,
        ),

    ),
    # QT-08W Solar Intelligent Water Valve
    "sfkzq": (
        XTBinarySensorEntityDescription(
            key=XTDPCode.MALFUNCTION,
            translation_key="error",
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            is_on=lambda x: x != 0,
        ),
        XTBinarySensorEntityDescription(
            key=XTDPCode.MALFUNCTION,
            subkey="0",
            translation_key="error_flow_meter",
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            is_on=lambda x: (x >> 0) & 1,
        ),
        XTBinarySensorEntityDescription(
            key=XTDPCode.MALFUNCTION,
            subkey="1",
            translation_key="error_valve_low_battery",
            device_class=BinarySensorDeviceClass.BATTERY,
            entity_category=EntityCategory.DIAGNOSTIC,
            is_on=lambda x: (x >> 1) & 1,
        ),
        XTBinarySensorEntityDescription(
            key=XTDPCode.MALFUNCTION,
            subkey="2",
            translation_key="error_sensor_low_battery",
            device_class=BinarySensorDeviceClass.BATTERY,
            entity_category=EntityCategory.DIAGNOSTIC,
            is_on=lambda x: (x >> 2) & 1,
        ),
        XTBinarySensorEntityDescription(
            key=XTDPCode.MALFUNCTION,
            subkey="3",
            translation_key="error_sensor_offline",
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            is_on=lambda x: (x >> 3) & 1,
        ),
        XTBinarySensorEntityDescription(
            key=XTDPCode.MALFUNCTION,
            subkey="4",
            translation_key="error_water_shortage",
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            is_on=lambda x: (x >> 4) & 1,
        ),
        XTBinarySensorEntityDescription(
            key=XTDPCode.MALFUNCTION,
            subkey="5",
            translation_key="error_other",
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_category=EntityCategory.DIAGNOSTIC,
            is_on=lambda x: (x >> 5) & 1,
        ),
        XTBinarySensorEntityDescription(
            key=XTDPCode.VBAT_STATE,
            translation_key="battery_charging",
            device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
            entity_category=EntityCategory.DIAGNOSTIC,
            is_on=lambda x: x > 127,
        ),
    ),
    "smd": (
        XTBinarySensorEntityDescription(
            key=XTDPCode.OFF,
            translation_key="off",
        ),
        XTBinarySensorEntityDescription(
            key=XTDPCode.OFF_BED,
            translation_key="off_bed",
        ),
        XTBinarySensorEntityDescription(
            key=XTDPCode.WAKEUP,
            translation_key="wakeup",
        ),
    ),
}

# Lock duplicates
BINARY_SENSORS["videolock"] = BINARY_SENSORS["jtmspro"]
BINARY_SENSORS["jtmsbh"] = BINARY_SENSORS["jtmspro"]


def _get_bitmap_bit_mask(
    device: XTDevice, dpcode: str, bitmap_key: str | None
) -> int | None:
    """Get the bit mask for a given bitmap description."""
    if (
        bitmap_key is None
        or (status_range := device.status_range.get(dpcode)) is None
        or status_range.type != TuyaDPType.BITMAP
        or not isinstance(bitmap_values := json_loads(status_range.values), dict)
        or not isinstance(bitmap_labels := bitmap_values.get("label"), list)
        or bitmap_key not in bitmap_labels
    ):
        return None
    return bitmap_labels.index(bitmap_key)


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya binary sensor dynamically through Tuya discovery."""
    hass_data = entry.runtime_data
    this_platform = Platform.BINARY_SENSOR

    if hass_data.manager is None:
        return
    if entry.runtime_data.multi_manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, tuple[XTBinarySensorEntityDescription, ...]],
            dict[str, tuple[XTBinarySensorEntityDescription, ...]],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            BINARY_SENSORS,
            entry.runtime_data.multi_manager,
            XTBinarySensorEntityDescription,
            this_platform,
            COMPOUND_KEY,
        ),
    )

    @callback
    def async_add_generic_entities(device_map) -> None:
        if hass_data.manager is None:
            return
        entities: list[XTBinarySensorEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                generic_dpcodes = XTEntity.get_generic_dpcodes_for_this_platform(
                    device, this_platform
                )
                for dpcode in generic_dpcodes:
                    if dpcode_information := device.get_dpcode_information(
                        dpcode=dpcode
                    ):
                        if (
                            dpcode_information.dptype is TuyaDPType.BITMAP
                            and len(dpcode_information.label) > 0
                        ):
                            for label_value in dpcode_information.label:
                                descriptor = XTBinarySensorEntityDescription(
                                    key=dpcode,
                                    subkey=label_value,
                                    bitmap_key=label_value,
                                    translation_key="xt_generic_binary_sensor",
                                    translation_placeholders={
                                        "name": f"{dpcode_information.human_name}: {XTEntity.get_human_name(label_value)}"
                                    },
                                    entity_registry_enabled_default=False,
                                    entity_registry_visible_default=False,
                                )
                                entities.append(
                                    XTBinarySensorEntity.get_entity_instance(
                                        descriptor, device, hass_data.manager
                                    )
                                )
                        else:
                            descriptor = XTBinarySensorEntityDescription(
                                key=dpcode,
                                translation_key="xt_generic_binary_sensor",
                                translation_placeholders={
                                    "name": dpcode_information.human_name
                                },
                                entity_registry_enabled_default=False,
                                entity_registry_visible_default=False,
                            )
                            entities.append(
                                XTBinarySensorEntity.get_entity_instance(
                                    descriptor, device, hass_data.manager
                                )
                            )
        async_add_entities(entities)

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered Tuya binary sensor."""
        entities: list[XTBinarySensorEntity] = []
        device_ids = [*device_map]
        if hass_data.manager is None:
            return
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id, None):
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
                            tuple[XTBinarySensorEntityDescription, ...],
                            restrict_descriptor_category(
                                category_descriptions, [restrict_dpcode]
                            ),
                        )
                    entities.extend(
                        XTBinarySensorEntity.get_entity_instance(
                            description, device, hass_data.manager
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device,
                            this_platform,
                            description,
                            True,
                            externally_managed_dpcodes,
                            COMPOUND_KEY,
                        )
                    )
                    entities.extend(
                        XTBinarySensorEntity.get_entity_instance(
                            description, device, hass_data.manager
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device,
                            this_platform,
                            description,
                            False,
                            externally_managed_dpcodes,
                            COMPOUND_KEY,
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
    # async_discover_device(hass_data.manager, hass_data.manager.open_api_device_map)

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTBinarySensorEntity(XTEntity, TuyaBinarySensorEntity):
    """XT Binary Sensor Entity."""

    _entity_description: XTBinarySensorEntityDescription

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTBinarySensorEntityDescription,
    ) -> None:
        """Init Tuya binary sensor."""
        super(XTBinarySensorEntity, self).__init__(device, device_manager, description)
        super(XTEntity, self).__init__(
            device,
            device_manager, # type: ignore
            description,
            _get_bitmap_bit_mask(
                device, description.dpcode or description.key, description.bitmap_key
            ),
        )
        self.device = device
        self.device_manager = device_manager
        self._entity_description = description
        # Append subkey to unique ID
        if description.subkey is not None and self._attr_unique_id is not None:
            self._attr_unique_id += f"{description.subkey}"

    @property
    def is_on(self) -> bool:
        # Use custom is_on function
        if self._entity_description.is_on is not None:
            is_on = self._entity_description.is_on(
                self.device.status[self.entity_description.key]
            )
        else:
            is_on = super().is_on
        if self._entity_description.device_online:
            dpcode = self.entity_description.dpcode or self.entity_description.key
            self.device.online_states[dpcode] = is_on
            self.device_manager.update_device_online_status(self.device.id)
        return is_on

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()
        self.is_on  # Update the online status if needed

    # def _name_internal(
    #    self,
    #    device_class_name: str | None,
    #    platform_translations: dict[str, str],
    # ) -> str | UndefinedType | None:
    #    name = super()._name_internal(device_class_name=device_class_name, platform_translations=platform_translations)
    #    if self.entity_description.translation_key != "xt_generic_binary_sensor":
    #        LOGGER.warning(f"Returning name for {self.device.name}=>{self.entity_description.key}: '{name}'")
    #    return name

    # @property
    # def _name_translation_key(self) -> str | None:
    #    name = super()._name_translation_key
    #    LOGGER.warning(f"Returning name TK for {self.device.name}=>{self.entity_description.key}: '{name}'")
    #    return name

    @staticmethod
    def get_entity_instance(
        description: XTBinarySensorEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
    ) -> XTBinarySensorEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(device, device_manager, description)
        return XTBinarySensorEntity(
            device,
            device_manager,
            XTBinarySensorEntityDescription(**description.__dict__),
        )
