"""Support for Tuya event entities."""

from __future__ import annotations
from typing import Any, cast
from datetime import datetime
from dataclasses import dataclass
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.event import (
    EventDeviceClass,
)
from homeassistant.components.event.const import (
    DoorbellEventType,
)
from tuya_device_handlers.definition.event import (
    TuyaEventDefinition,
    get_default_definition,
)
from tuya_device_handlers.device_wrapper.common import (
    DPCodeIntegerWrapper,
    DPCodeBooleanWrapper,
    DPCodeJsonWrapper,
    DPCodeStringWrapper,
    DPCodeTypeInformationWrapper,
    DPCodeRawWrapper,
)
from tuya_device_handlers.device_wrapper.event import (
    SimpleEventEnumWrapper,
)
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
    LOGGER,
    XTDPCode,
    XTDeviceWatcherCategory,  # noqa: F401
    VirtualStates,
    CROSS_CATEGORY_DEVICE_DESCRIPTOR,
    XT_DEVICE_EVENT_NOTIFY_DPCODE,
    XTGlobalEvents,
    XT_GLOBAL_EVENT_PREFIX,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaEventEntity,
    TuyaEventEntityDescription,
    TuyaCustomerDevice,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)


class XTJSONEventWrapper(DPCodeJsonWrapper[tuple[str, dict[str, Any]]]):
    def __init__(self, dpcode: str, type_information: Any) -> None:
        super().__init__(dpcode, type_information)
        self.options = [f"{self.dpcode}"]

    def read_device_status(
        self, device: TuyaCustomerDevice
    ) -> tuple[str, dict[str, Any]] | None:
        """Return the event with message attribute."""
        status = self._read_dpcode_value(device)
        if status is None:
            return None
        return (f"{self.dpcode}", status)

    def skip_update(
        self,
        device: TuyaCustomerDevice,
        updated_status_properties: list[str],
        dp_timestamps: dict[str, int] | None = None,
    ) -> bool:
        return super().skip_update(
            device=device,
            updated_status_properties=updated_status_properties,
            dp_timestamps=dp_timestamps,
        )


class XTIntegerEventWrapper(DPCodeIntegerWrapper[tuple[str, dict[str, Any]]]):
    def __init__(self, dpcode: str, type_information: Any) -> None:
        super().__init__(dpcode, type_information)
        self.options = [f"{self.dpcode}"]

    def read_device_status(
        self, device: TuyaCustomerDevice
    ) -> tuple[str, dict[str, Any]] | None:
        """Return the event with message attribute."""
        if (status := self._read_dpcode_value(device)) is None:
            return None
        return (f"{self.dpcode}", {"value": status, "changed_time": datetime.now()})


class XTBooleanEventWrapper(DPCodeBooleanWrapper[tuple[str, dict[str, Any]]]):
    def __init__(self, dpcode: str, type_information: Any) -> None:
        super().__init__(dpcode, type_information)
        self.options = [f"{self.dpcode}"]

    def read_device_status(
        self, device: TuyaCustomerDevice
    ) -> tuple[str, dict[str, Any]] | None:
        """Return the event with message attribute."""
        if (status := self._read_dpcode_value(device)) is None:
            return None
        return (f"{self.dpcode}", {"value": status, "changed_time": datetime.now()})


class XTDoorbellBooleanEventWrapper(XTBooleanEventWrapper):
    def __init__(self, dpcode: str, type_information: Any) -> None:
        super().__init__(dpcode, type_information)
        self.options = [f"{self.dpcode}", DoorbellEventType.RING]


class XTRawEventWrapper(DPCodeRawWrapper[tuple[str, dict[str, Any]]]):
    def __init__(self, dpcode: str, type_information: Any) -> None:
        super().__init__(dpcode, type_information)
        self.options = [f"{self.dpcode}"]

    def read_device_status(
        self, device: TuyaCustomerDevice
    ) -> tuple[str, dict[str, Any]] | None:
        """Return the event with message attribute."""
        if (status := self._read_dpcode_value(device)) is None:
            return None
        return (f"{self.dpcode}", {"value": status, "changed_time": datetime.now()})


class XTStringEventWrapper(DPCodeStringWrapper[tuple[str, dict[str, Any]]]):
    def __init__(self, dpcode: str, type_information: Any) -> None:
        super().__init__(dpcode, type_information)
        self.options = [f"{self.dpcode}"]

    def read_device_status(
        self, device: TuyaCustomerDevice
    ) -> tuple[str, dict[str, Any]] | None:
        """Return the event with message attribute."""
        if (status := self._read_dpcode_value(device)) is None:
            return None
        return (f"{self.dpcode}", {"value": status, "changed_time": datetime.now()})


class XTDoorbellStringEventWrapper(XTStringEventWrapper):
    def __init__(self, dpcode: str, type_information: Any) -> None:
        super().__init__(dpcode, type_information)
        self.options = [f"{self.dpcode}", DoorbellEventType.RING]


def xt_get_default_definition(
    device: XTDevice,
    dpcode: str,
    wrapper_classes: type[DPCodeTypeInformationWrapper] | tuple[type[DPCodeTypeInformationWrapper], ...],  # type: ignore[type-arg]
) -> TuyaEventDefinition | None:
    if isinstance(wrapper_classes, tuple):
        for wrapper_class in wrapper_classes:
            if wrapper := wrapper_class.find_dpcode(device, dpcode):
                return TuyaEventDefinition(
                    event_wrapper=wrapper,
                )
    else:
        return get_default_definition(
            device=device, dpcode=dpcode, wrapper_class=wrapper_classes
        )
    return None


@dataclass(frozen=True)
class XTEventEntityDescription(TuyaEventEntityDescription):
    wrapper_class: type[DPCodeTypeInformationWrapper] | tuple[type[DPCodeTypeInformationWrapper], ...] = SimpleEventEnumWrapper  # type: ignore

    override_tuya: bool = False
    dont_send_to_cloud: bool = False
    on_value: Any = None
    off_value: Any = None
    trigger_global_event: XTGlobalEvents | tuple[XTGlobalEvents, ...] | None = None

    # duplicate the entity if handled by another integration
    ignore_other_dp_code_handler: bool = False
    virtual_state: VirtualStates | None = VirtualStates.STATE_DEDUPLICATE_IN_REPORTING

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTEventEntityDescription,
        definition: TuyaEventDefinition,
    ) -> XTEventEntity:
        return XTEventEntity(
            device=device,
            device_manager=device_manager,
            description=XTEventEntityDescription(**description.__dict__),
            definition=definition,
        )


# All descriptions can be found here. Mostly the Enum data types in the
# default status set of each category (that don't have a set instruction)
# end up being events.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
EVENTS: dict[str, tuple[XTEventEntityDescription, ...]] = {
    CROSS_CATEGORY_DEVICE_DESCRIPTOR: (
        XTEventEntityDescription(
            key=XTDPCode.ALARM_LOCK,
            translation_key="alarm_lock",
            device_class=None,
        ),
        XTEventEntityDescription(
            key=XTDPCode.ALARM_MESSAGE,
            device_class=EventDeviceClass.DOORBELL,
            translation_key="doorbell_message",
            wrapper_class=XTDoorbellStringEventWrapper,
        ),
        XTEventEntityDescription(
            key=XTDPCode.DOORBELL_PIC,
            device_class=EventDeviceClass.DOORBELL,
            translation_key="doorbell_picture",
            wrapper_class=XTDoorbellStringEventWrapper,
        ),
        XTEventEntityDescription(
            key=XTDPCode.CARD_UNLOCK_USER,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Card"},
            device_class=None,
            wrapper_class=XTIntegerEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.DOORBELL,
            translation_key="doorbell",
            device_class=EventDeviceClass.DOORBELL,
            wrapper_class=XTDoorbellBooleanEventWrapper,
        ),
        XTEventEntityDescription(
            key=XTDPCode.FACE_UNLOCK_USER,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Face"},
            device_class=None,
            wrapper_class=XTIntegerEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.FINGERPRINT_UNLOCK_USER,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Fingerprint"},
            device_class=None,
            wrapper_class=XTIntegerEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.HAND_UNLOCK_USER,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Hand"},
            device_class=None,
            wrapper_class=XTIntegerEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.IPC_MOVEMENT_DETECT,
            translation_key="ipc_movement_detect",
            device_class=EventDeviceClass.MOTION,
        ),
        XTEventEntityDescription(
            key=XTDPCode.PASSWORD_UNLOCK_USER,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Password"},
            device_class=None,
            wrapper_class=XTIntegerEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.UNLOCK_BLE,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Bluetooth"},
            device_class=None,
            wrapper_class=XTIntegerEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.UNLOCK_CARD,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Card"},
            device_class=None,
            wrapper_class=XTIntegerEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.UNLOCK_CARD_KIT,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Card"},
            device_class=None,
            wrapper_class=XTStringEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.UNLOCK_DYNAMIC,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Dynamic"},
            device_class=None,
            wrapper_class=XTIntegerEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.UNLOCK_FACE,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Face"},
            device_class=None,
            wrapper_class=XTIntegerEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.UNLOCK_FINGERPRINT,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Fingerprint"},
            device_class=None,
            wrapper_class=XTIntegerEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.UNLOCK_FINGERPRINT_KIT,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Fingerprint"},
            device_class=None,
            wrapper_class=XTStringEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.UNLOCK_FINGER_VEIN,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Finger vein"},
            device_class=None,
            wrapper_class=XTIntegerEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.UNLOCK_HAND,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Hand"},
            device_class=None,
            wrapper_class=XTIntegerEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.UNLOCK_KEY,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Key"},
            device_class=None,
            wrapper_class=XTIntegerEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.UNLOCK_OFFLINE_PD,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Offline password"},
            device_class=None,
            wrapper_class=XTStringEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.UNLOCK_PASSWORD,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Password"},
            device_class=None,
            wrapper_class=XTIntegerEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.UNLOCK_PASSWORD_KIT,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Password"},
            device_class=None,
            wrapper_class=XTStringEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.UNLOCK_PHONE_REMOTE,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Phone"},
            device_class=None,
            wrapper_class=XTIntegerEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.UNLOCK_PHONE_REMOTE_KIT,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Phone"},
            device_class=None,
            wrapper_class=XTStringEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.UNLOCK_TELECONTROL_KIT,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Remote control"},
            device_class=None,
            wrapper_class=XTStringEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.UNLOCK_TEMPORARY,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Temporary"},
            device_class=None,
            wrapper_class=XTIntegerEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.UNLOCK_TEMPORARY_KIT,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Temporary"},
            device_class=None,
            wrapper_class=XTStringEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XTDPCode.UNLOCK_VOICE_REMOTE,
            translation_key="unlock_user",
            translation_placeholders={"user_type": "Voice"},
            device_class=None,
            wrapper_class=XTIntegerEventWrapper,
            trigger_global_event=XTGlobalEvents.LOCK_UNLOCKED,
        ),
        XTEventEntityDescription(
            key=XT_DEVICE_EVENT_NOTIFY_DPCODE,
            translation_key="xt_device_event_notify",
            device_class=None,
            wrapper_class=XTJSONEventWrapper,
            entity_registry_visible_default=False,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up tuya sensors dynamically through tuya discovery."""
    hass_data = entry.runtime_data
    this_platform = Platform.EVENT

    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, tuple[XTEventEntityDescription, ...]],
            dict[str, tuple[XTEventEntityDescription, ...]],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            EVENTS,
            entry.runtime_data.multi_manager,
            XTEventEntityDescription,
            this_platform,
        ),
    )

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered tuya sensor."""
        if hass_data.manager is None:
            return
        entities: list[XTEventEntity] = []
        device_ids = [*device_map]
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
                            tuple[XTEventEntityDescription, ...],
                            restrict_descriptor_category(
                                category_descriptions, [restrict_dpcode]
                            ),
                        )
                    entities.extend(
                        XTEventEntity.get_entity_instance(
                            device=device,
                            device_manager=hass_data.manager,
                            description=description,
                            definition=definition,
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
                                definition := xt_get_default_definition(
                                    device, description.key, description.wrapper_class
                                )
                            )
                        )
                    )
                    entities.extend(
                        XTEventEntity.get_entity_instance(
                            device=device,
                            device_manager=hass_data.manager,
                            description=description,
                            definition=definition,
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
                                definition := xt_get_default_definition(
                                    device, description.key, description.wrapper_class
                                )
                            )
                        )
                    )

        async_add_entities(entities)

    hass_data.manager.register_device_descriptors(this_platform, supported_descriptors)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class XTEventEntity(XTEntity, TuyaEventEntity):
    """Tuya Event Entity."""

    entity_description: XTEventEntityDescription

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTEventEntityDescription,
        definition: TuyaEventDefinition,
    ) -> None:
        """Init Tuya event entity."""
        try:
            super(XTEventEntity, self).__init__(
                device=device,
                device_manager=device_manager,  # type: ignore
                description=description,
                definition=definition,
            )
            super(XTEntity, self).__init__(
                device=device,
                device_manager=device_manager,  # type: ignore
                description=description,
                definition=definition,
            )
        except Exception as e:
            LOGGER.warning(f"Events failed to initialize, is your HA up to date? ({e})")
        self.device = device
        self.device_manager = device_manager
        self.entity_description = description  # type: ignore

    async def _process_device_update(
        self,
        updated_status_properties: list[str],
        dp_timestamps: dict[str, int] | None,
    ) -> bool:
        event_sent = await super()._process_device_update(
            updated_status_properties=updated_status_properties,
            dp_timestamps=dp_timestamps,
        )
        if event_sent is False:
            return event_sent
        if self.entity_description.trigger_global_event is not None:
            if isinstance(self.entity_description.trigger_global_event, tuple):
                for event in self.entity_description.trigger_global_event:
                    dispatcher_send(
                        self.hass,
                        f"{XT_GLOBAL_EVENT_PREFIX}{event}",
                        self.device.id,
                    )
            elif isinstance(self.entity_description.trigger_global_event, str):
                dispatcher_send(
                        self.hass,
                        f"{XT_GLOBAL_EVENT_PREFIX}{self.entity_description.trigger_global_event}",
                        self.device.id,
                    )
        return event_sent

    @property
    def state_attributes(self) -> dict[str, Any]:  # type: ignore
        """Return the state attributes."""
        try:
            return super().state_attributes
        except Exception:
            return {}

    @staticmethod
    def get_entity_instance(
        device: XTDevice,
        device_manager: MultiManager,
        description: XTEventEntityDescription,
        definition: TuyaEventDefinition,
    ) -> XTEventEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(
                device=device,
                device_manager=device_manager,
                description=description,
                definition=definition,
            )
        return XTEventEntity(
            device=device,
            device_manager=device_manager,
            description=XTEventEntityDescription(**description.__dict__),
            definition=definition,
        )
