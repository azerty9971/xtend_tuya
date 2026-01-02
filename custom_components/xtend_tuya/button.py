"""Support for XT buttons."""

from __future__ import annotations
from typing import cast, Any
from dataclasses import dataclass, field
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .util import (
    restrict_descriptor_category,
    delete_all_device_entities,
)
from .multi_manager.multi_manager import (
    XTConfigEntry,
    MultiManager,
    XTDevice,
)
from .multi_manager.shared.threading import (
    XTEventLoopProtector,
)
from .const import (
    TUYA_DISCOVERY_NEW,
    XTDPCode,
    VirtualFunctions,
    XTMultiManagerPostSetupCallbackPriority,
    XTIRHubInformation,
    XTIRRemoteInformation,
    XTIRRemoteKeysInformation,
    XTMultiManagerProperties,
    XTDiscoverySource,
    LOGGER,  # noqa: F401
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaButtonEntity,
    TuyaButtonEntityDescription,
    TuyaDPCodeBooleanWrapper,
    TuyaDPCodeWrapper,
    TuyaCustomerDevice,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)

from .multi_manager.shared.data_entry.ir_device_data_entry import (
    XTDataEntryAddIRDevice,
    XTDataEntryAddIRDeviceKey,
    XTDataEntryManager,
)


class XTIRActionDPCodeWrapper(TuyaDPCodeWrapper):
    """XT IR Action DPCode Wrapper."""

    def __init__(
        self, description: XTButtonEntityDescription, multi_manager: MultiManager, device: XTDevice
    ) -> None:
        super().__init__(description.key)
        self.multi_manager = multi_manager
        self.description = description
        self.device = device
        self.button_press_handler: XTDataEntryManager | None = None
        if (
            self.description.is_ir_descriptor
            and self.description.ir_remote_information is not None
            and self.description.ir_hub_information is not None
        ):
            self.button_press_handler = XTDataEntryAddIRDeviceKey(
                source=XTDiscoverySource.SOURCE_ADD_IR_DEVICE_KEY,
                hass=multi_manager.hass,
                multi_manager=multi_manager,
                device=device,
                hub=self.description.ir_hub_information,
                remote=self.description.ir_remote_information,
            )
        elif (
            self.description.is_ir_descriptor
            and self.description.ir_hub_information is not None
        ):
            self.button_press_handler = XTDataEntryAddIRDevice(
                source=XTDiscoverySource.SOURCE_ADD_IR_DEVICE,
                hass=multi_manager.hass,
                multi_manager=multi_manager,
                device=device,
                hub=self.description.ir_hub_information,
            )

    def _convert_value_to_raw_value(
        self, device: TuyaCustomerDevice, value: bool
    ) -> Any:
        """Convert a Home Assistant value back to a raw device value."""
        return True  # Always send True to trigger the action

    def get_update_commands( # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        device: XTDevice,
        value: Any,
    ) -> list[dict[str, Any]]:
        if (
            self.description.is_ir_descriptor
            and self.description.ir_key_information is not None
            and self.description.ir_remote_information is not None
            and self.description.ir_hub_information is not None
        ):
            self.multi_manager.send_ir_command(
                device,
                self.description.ir_key_information,
                self.description.ir_remote_information,
                self.description.ir_hub_information,
            )
        elif self.button_press_handler is not None:
            self.button_press_handler.fire_event()
        return []


@dataclass(frozen=True)
class XTButtonEntityDescription(TuyaButtonEntityDescription):
    virtual_function: VirtualFunctions | None = None
    vf_reset_state: list[XTDPCode] | None = field(default_factory=list)
    is_ir_descriptor: bool = False
    ir_hub_information: XTIRHubInformation | None = None
    ir_remote_information: XTIRRemoteInformation | None = None
    ir_key_information: XTIRRemoteKeysInformation | None = None

    # duplicate the entity if handled by another integration
    ignore_other_dp_code_handler: bool = False

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTButtonEntityDescription,
        dpcode_wrapper: TuyaDPCodeBooleanWrapper,
    ) -> XTButtonEntity:
        return XTButtonEntity(
            device=device,
            device_manager=device_manager,
            description=XTButtonEntityDescription(**description.__dict__),
            dpcode_wrapper=dpcode_wrapper,
        )


IR_HUB_CATEGORY_LIST: list[str] = [
    "wnykq",
]

CONSUMPTION_BUTTONS: tuple[XTButtonEntityDescription, ...] = (
    XTButtonEntityDescription(
        key=XTDPCode.RESET_ADD_ELE,
        virtual_function=VirtualFunctions.FUNCTION_RESET_STATE,
        vf_reset_state=[XTDPCode.ADD_ELE],
        translation_key="reset_add_ele",
        entity_category=EntityCategory.CONFIG,
    ),
)

# All descriptions can be found here.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
BUTTONS: dict[str, tuple[XTButtonEntityDescription, ...]] = {
    "jtmspro": (
        XTButtonEntityDescription(
            key=XTDPCode.MANUAL_LOCK,
            translation_key="manual_lock",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "kg": (*CONSUMPTION_BUTTONS,),
    "msp": (
        XTButtonEntityDescription(
            key=XTDPCode.BAG_CHANGE_MODE,
            translation_key="change_litter_bag",
            entity_category=EntityCategory.CONFIG,
        ),
        # Poopy Nano 2 uses the DPCode "clean" for starting a manual clean.
        # We reuse the same translation key.
        XTButtonEntityDescription(
            key=XTDPCode.CLEAN,
            translation_key="manual_clean",
            entity_category=EntityCategory.CONFIG,
        ),
        XTButtonEntityDescription(
            key=XTDPCode.EMPTY,
            translation_key="empty_litter",
            entity_category=EntityCategory.CONFIG,
        ),
        XTButtonEntityDescription(
            key=XTDPCode.FACTORY_RESET,
            translation_key="factory_reset",
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
        ),
        XTButtonEntityDescription(
            key=XTDPCode.LEVEL_CAT_LITTER,
            translation_key="level_cat_litter",
            entity_category=EntityCategory.CONFIG,
        ),
        # ZEDAR K1200 uses the DPCode "manual_clean" for starting a manual clean.
        # We reuse the same translation key.
        XTButtonEntityDescription(
            key=XTDPCode.MANUAL_CLEAN,
            translation_key="manual_clean",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "qccdz": (
        XTButtonEntityDescription(
            key=XTDPCode.CLEAR_ENERGY,
            translation_key="clear_energy",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
    "xfj": (
        XTButtonEntityDescription(
            key=XTDPCode.FILTER_RESET,
            translation_key="filter_reset",
            entity_category=EntityCategory.CONFIG,
        ),
    ),
}

BUTTONS["cz"] = BUTTONS["kg"]
BUTTONS["wkcz"] = BUTTONS["kg"]
BUTTONS["dlq"] = BUTTONS["kg"]
BUTTONS["tdq"] = BUTTONS["kg"]
BUTTONS["pc"] = BUTTONS["kg"]
BUTTONS["aqcz"] = BUTTONS["kg"]

# Lock duplicates
BUTTONS["videolock"] = BUTTONS["jtmspro"]
BUTTONS["jtmsbh"] = BUTTONS["jtmspro"]


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya buttons dynamically through Tuya discovery."""
    hass_data = entry.runtime_data
    this_platform = Platform.BUTTON

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, tuple[XTButtonEntityDescription, ...]],
            dict[str, tuple[XTButtonEntityDescription, ...]],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            BUTTONS,
            entry.runtime_data.multi_manager,
            XTButtonEntityDescription,
            this_platform,
        ),
    )

    @callback
    async def async_add_IR_entities(device_map) -> None:
        if hass_data.manager is None:
            return
        entities: list[XTButtonEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if hub_device := hass_data.manager.device_map.get(device_id):
                if hub_device.category in IR_HUB_CATEGORY_LIST:
                    hub_information: XTIRHubInformation | None = (
                        await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                            hass_data.manager.get_ir_hub_information, hub_device
                        )
                    )
                    if hub_information is None:
                        continue

                    # First, clean up the device and subdevices
                    entity_cleanup_device_ids: list[str] = [hub_information.device_id]
                    for remote_information in hub_information.remote_ids:
                        entity_cleanup_device_ids.append(remote_information.remote_id)
                    delete_all_device_entities(
                        hass, entity_cleanup_device_ids, this_platform
                    )

                    descriptor = XTButtonEntityDescription(
                        key="xt_add_ir_device",
                        translation_key="xt_add_ir_device",
                        is_ir_descriptor=True,
                        ir_hub_information=hub_information,
                        ir_remote_information=None,
                        ir_key_information=None,
                        entity_category=EntityCategory.CONFIG,
                        entity_registry_enabled_default=True,
                        entity_registry_visible_default=True,
                    )
                    dpcode_wrapper = XTIRActionDPCodeWrapper(
                        descriptor, hass_data.manager, hub_device
                    )
                    entities.append(
                        XTButtonEntity.get_entity_instance(
                            descriptor,
                            hub_device,
                            hass_data.manager,
                            dpcode_wrapper, # type: ignore
                        )
                    )

                    for remote_information in hub_information.remote_ids:
                        if remote_device := hass_data.manager.device_map.get(
                            remote_information.remote_id
                        ):
                            descriptor = XTButtonEntityDescription(
                                key="xt_add_ir_device_key",
                                translation_key="xt_add_ir_device_key",
                                is_ir_descriptor=True,
                                ir_hub_information=hub_information,
                                ir_remote_information=remote_information,
                                ir_key_information=None,
                                entity_category=EntityCategory.CONFIG,
                                entity_registry_enabled_default=True,
                                entity_registry_visible_default=True,
                            )
                            dpcode_wrapper = XTIRActionDPCodeWrapper(
                                descriptor, hass_data.manager, hub_device
                            )
                            entities.append(
                                XTButtonEntity.get_entity_instance(
                                    descriptor,
                                    remote_device,
                                    hass_data.manager,
                                    dpcode_wrapper, # type: ignore
                                )
                            )
                            for remote_key in remote_information.keys:
                                descriptor = XTButtonEntityDescription(
                                    key=f"xt_ir_key_{remote_key.key}",
                                    translation_key="xt_generic_button",
                                    translation_placeholders={
                                        "name": remote_key.key_name
                                    },
                                    is_ir_descriptor=True,
                                    ir_hub_information=hub_information,
                                    ir_remote_information=remote_information,
                                    ir_key_information=remote_key,
                                    entity_registry_enabled_default=True,
                                    entity_registry_visible_default=True,
                                )
                                dpcode_wrapper = XTIRActionDPCodeWrapper(
                                    descriptor, hass_data.manager, hub_device
                                )
                                entities.append(
                                    XTButtonEntity.get_entity_instance(
                                        descriptor,
                                        remote_device,
                                        hass_data.manager,
                                        dpcode_wrapper, # type: ignore
                                    )
                                )
        async_add_entities(entities)

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered Tuya buttons."""
        if hass_data.manager is None:
            return
        entities: list[XTButtonEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if device.category in IR_HUB_CATEGORY_LIST:
                    hass_data.manager.set_general_property(
                        XTMultiManagerProperties.IR_DEVICE_ID, device.id
                    )
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
                            tuple[XTButtonEntityDescription, ...],
                            restrict_descriptor_category(
                                category_descriptions, [restrict_dpcode]
                            ),
                        )
                    entities.extend(
                        XTButtonEntity.get_entity_instance(
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
                        XTButtonEntity.get_entity_instance(
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
                    for description in category_descriptions:
                        if (
                            hasattr(description, "vf_reset_state")
                            and description.vf_reset_state
                        ):
                            for reset_state in description.vf_reset_state:
                                if reset_state in device.status:
                                    if dpcode_wrapper := TuyaDPCodeBooleanWrapper.find_dpcode(
                                        device,
                                        description.key,
                                        prefer_function=True,
                                    ):
                                        entities.append(
                                            XTButtonEntity.get_entity_instance(
                                                description,
                                                device,
                                                hass_data.manager,
                                                dpcode_wrapper,
                                            )
                                        )
                                break

        async_add_entities(entities)
        if restrict_dpcode is None:
            hass_data.manager.add_post_setup_callback(
                XTMultiManagerPostSetupCallbackPriority.PRIORITY_LAST,
                async_add_IR_entities,
                device_map,
            )

    hass_data.manager.register_device_descriptors(this_platform, supported_descriptors)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTButtonEntity(XTEntity, TuyaButtonEntity):
    """XT Button Device."""

    _entity_description: XTButtonEntityDescription

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTButtonEntityDescription,
        dpcode_wrapper: TuyaDPCodeBooleanWrapper,
    ) -> None:
        """Init XT button."""
        super(XTButtonEntity, self).__init__(
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
        self.entity_description = description
        self._entity_description = description

    @staticmethod
    def get_entity_instance(
        description: XTButtonEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
        dpcode_wrapper: TuyaDPCodeBooleanWrapper,
    ) -> XTButtonEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(
                device, device_manager, description, dpcode_wrapper
            )
        return XTButtonEntity(
            device,
            device_manager,
            XTButtonEntityDescription(**description.__dict__),
            dpcode_wrapper,
        )
