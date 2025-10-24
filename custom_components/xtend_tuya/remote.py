from __future__ import annotations
from typing import cast, Any
from dataclasses import dataclass
from collections.abc import Iterable
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.remote import (
    RemoteEntity,
    RemoteEntityDescription,
    RemoteEntityFeature,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import EntityCategory, Platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .const import (
    TUYA_DISCOVERY_NEW,
    XTMultiManagerPostSetupCallbackPriority,
    XTIRHubInformation,
    XTIRRemoteInformation,
    XTIRRemoteKeysInformation,
    LOGGER,
)
from .util import (
    restrict_descriptor_category,
    delete_all_device_entities,
)
from .multi_manager.multi_manager import (
    MultiManager,
    XTConfigEntry,
    XTDevice,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)
from .multi_manager.shared.threading import (
    XTEventLoopProtector,
)


@dataclass(frozen=True)
class XTRemoteEntityDescription(RemoteEntityDescription):
    """Describes a Tuya remote."""
    ir_hub_information: XTIRHubInformation | None = None
    ir_remote_information: XTIRRemoteInformation | None = None
    ir_key_information: XTIRRemoteKeysInformation | None = None

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTRemoteEntityDescription,
    ) -> XTRemoteEntity:
        return XTRemoteEntity(
            device=device,
            device_manager=device_manager,
            description=XTRemoteEntityDescription(**description.__dict__),
        )


REMOTES: dict[str, tuple[XTRemoteEntityDescription, ...]] = {}
IR_HUB_CATEGORY_LIST: list[str] = [
    "wnykq",
]

async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya binary sensor dynamically through Tuya discovery."""
    hass_data = entry.runtime_data
    this_platform = Platform.REMOTE

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, tuple[XTRemoteEntityDescription, ...]],
            dict[str, tuple[XTRemoteEntityDescription, ...]],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            REMOTES, entry.runtime_data.multi_manager, this_platform
        ),
    )

    @callback
    async def async_add_IR_entities(device_map) -> None:
        if hass_data.manager is None:
            return
        entities: list[XTRemoteEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if hub_device := hass_data.manager.device_map.get(device_id):
                if hub_device.category in IR_HUB_CATEGORY_LIST:
                    hub_information: (
                        XTIRHubInformation | None
                    ) = await XTEventLoopProtector.execute_out_of_event_loop_and_return(
                        hass_data.manager.get_ir_hub_information, hub_device
                    )
                    if hub_information is None:
                        continue

                    # First, clean up the device and subdevices
                    entity_cleanup_device_ids: list[str] = [hub_information.device_id]
                    for remote_information in hub_information.remote_ids:
                        entity_cleanup_device_ids.append(remote_information.remote_id)
                    delete_all_device_entities(hass, entity_cleanup_device_ids)

                    descriptor = XTRemoteEntityDescription(
                        key="xt_add_device",
                        translation_key="xt_add_ir_device",
                        ir_hub_information=hub_information,
                        ir_remote_information=None,
                        ir_key_information=None,
                        entity_category=EntityCategory.CONFIG,
                        entity_registry_enabled_default=True,
                        entity_registry_visible_default=True,
                    )
                    entities.append(
                        XTRemoteEntity.get_entity_instance(
                            descriptor, hub_device, hass_data.manager
                        )
                    )

                    for remote_information in hub_information.remote_ids:
                        if remote_device := hass_data.manager.device_map.get(
                            remote_information.remote_id
                        ):
                            descriptor = XTRemoteEntityDescription(
                                key="xt_add_device_key",
                                translation_key="xt_add_ir_device_key",
                                ir_hub_information=hub_information,
                                ir_remote_information=remote_information,
                                ir_key_information=None,
                                entity_category=EntityCategory.CONFIG,
                                entity_registry_enabled_default=True,
                                entity_registry_visible_default=True,
                            )
                            entities.append(
                                XTRemoteEntity.get_entity_instance(
                                    descriptor, remote_device, hass_data.manager
                                )
                            )
                            for remote_key in remote_information.keys:
                                descriptor = XTRemoteEntityDescription(
                                    key=remote_key.key,
                                    translation_key="xt_generic_button",
                                    translation_placeholders={
                                        "name": remote_key.key
                                    },
                                    ir_hub_information=hub_information,
                                    ir_remote_information=remote_information,
                                    ir_key_information=remote_key,
                                    entity_registry_enabled_default=True,
                                    entity_registry_visible_default=True,
                                )
                                entities.append(
                                    XTRemoteEntity.get_entity_instance(
                                        descriptor, remote_device, hass_data.manager
                                    )
                                )
        async_add_entities(entities)

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered Tuya binary sensor."""
        if hass_data.manager is None:
            return
        entities: list[XTRemoteEntity] = []
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
                            tuple[XTRemoteEntityDescription, ...],
                            restrict_descriptor_category(
                                category_descriptions, [restrict_dpcode]
                            ),
                        )
                    entities.extend(
                        XTRemoteEntity.get_entity_instance(
                            description, device, hass_data.manager
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device,
                            this_platform,
                            description,
                            True,
                            externally_managed_dpcodes,
                        )
                    )
                    entities.extend(
                        XTRemoteEntity.get_entity_instance(
                            description, device, hass_data.manager
                        )
                        for description in category_descriptions
                        if XTEntity.supports_description(
                            device,
                            this_platform,
                            description,
                            False,
                            externally_managed_dpcodes,
                        )
                    )

        async_add_entities(entities)
        if restrict_dpcode is None:
            hass_data.manager.add_post_setup_callback(
                XTMultiManagerPostSetupCallbackPriority.PRIORITY_LAST,
                async_add_IR_entities,
                device_map,
            )

    hass_data.manager.register_device_descriptors(this_platform, supported_descriptors)
    async_discover_device([*hass_data.manager.device_map])
    # async_discover_device(hass_data.manager, hass_data.manager.open_api_device_map)

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTRemoteEntity(XTEntity, RemoteEntity):  # type: ignore
    """XT Remote entity."""

    entity_description: XTRemoteEntityDescription

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTRemoteEntityDescription,
    ) -> None:
        """Init XT remote."""
        super(XTRemoteEntity, self).__init__(device, device_manager)
        self.entity_description = description  # type: ignore
        self.device = device
        self.device_manager = device_manager
        self._attr_unique_id = f"{super().unique_id}_remote_{description.key}"
        self._attr_supported_features = (
            RemoteEntityFeature.LEARN_COMMAND | RemoteEntityFeature.DELETE_COMMAND | RemoteEntityFeature.ACTIVITY
        )
        if description.ir_remote_information is not None and description.ir_remote_information.keys is not None:
            self._attr_activity_list: list[str] | None = []
            for key in description.ir_remote_information.keys:
                self._attr_activity_list.append(key.key_name)

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        LOGGER.warning(f"async_send_command => {self.device.name} <=> {command} <=> {kwargs}")
    
    async def async_learn_command(self, **kwargs: Any) -> None:
        LOGGER.warning(f"async_learn_command => {self.device.name} <=> {kwargs}")
    
    async def async_delete_command(self, **kwargs: Any) -> None:
        LOGGER.warning(f"async_delete_command => {self.device.name} <=> {kwargs}")

    @staticmethod
    def get_entity_instance(
        description: XTRemoteEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
    ) -> XTRemoteEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(device, device_manager, description)
        return XTRemoteEntity(
            device, device_manager, XTRemoteEntityDescription(**description.__dict__)
        )
