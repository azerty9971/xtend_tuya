from __future__ import annotations
from typing import overload, Literal, cast, Any
from enum import StrEnum
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers import entity_registry as er, device_registry as dr
from homeassistant.helpers.entity_registry import (
    RegistryEntryDisabler,
)
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from .const import (
    XTDPCode,
    LOGGER,
    CROSS_CATEGORY_DEVICE_DESCRIPTOR,
    DOMAIN,
    DOMAIN_ORIG,
    FULLY_OVERRIDEN_PLATFORMS,
)
import custom_components.xtend_tuya.multi_manager.shared.shared_classes as sc
import custom_components.xtend_tuya.multi_manager.multi_manager as mm
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaEnumTypeData,
    TuyaIntegerTypeData,
    TUYA_DPTYPE_MAPPING,
    TuyaEntity,
    TuyaDPCode,
    TuyaDPType,
)


class XTEntityDescriptorManager:
    class XTEntityDescriptorType(StrEnum):
        DICT = "dict"
        LIST = "list"
        TUPLE = "tuple"
        SET = "set"
        ENTITY = "entity"
        STRING = "string"
        UNKNOWN = "unknown"

    entity_type = (type(EntityDescription(key="")), EntityDescription)

    @staticmethod
    def get_platform_descriptors(
        platform_descriptors: Any,
        multi_manager: mm.MultiManager,
        descriptor_type: type[Any] | None,
        platform: Platform | None,
        key_fields: list[str] = ["key"],
    ) -> tuple[Any, Any]:
        include_descriptors = platform_descriptors
        exclude_descriptors = XTEntityDescriptorManager.get_empty_descriptor(
            platform_descriptors
        )
        if platform is not None:
            for descriptors_to_add in multi_manager.get_platform_descriptors_to_merge(
                platform
            ):
                include_descriptors = XTEntityDescriptorManager.merge_descriptors(
                    include_descriptors, descriptors_to_add, key_fields, descriptor_type
                )
            for (
                descriptors_to_exclude
            ) in multi_manager.get_platform_descriptors_to_exclude(platform):
                exclude_descriptors = XTEntityDescriptorManager.merge_descriptors(
                    exclude_descriptors,
                    descriptors_to_exclude,
                    key_fields,
                    descriptor_type,
                )
        return include_descriptors, exclude_descriptors

    @staticmethod
    def get_category_descriptors(descriptor_dict: dict[str, Any], category: str) -> Any:
        if not descriptor_dict:
            return None

        if category in descriptor_dict:
            return descriptor_dict[category]
        if CROSS_CATEGORY_DEVICE_DESCRIPTOR in descriptor_dict:
            return descriptor_dict[CROSS_CATEGORY_DEVICE_DESCRIPTOR]

    @staticmethod
    def get_category_keys(
        category_content: Any, key_fields: list[str] = ["key"]
    ) -> list[str]:
        return_list: list[str] = []
        if not category_content:
            return return_list
        ref_type = XTEntityDescriptorManager._get_param_type(category_content)
        if (
            ref_type is XTEntityDescriptorManager.XTEntityDescriptorType.LIST
            or ref_type is XTEntityDescriptorManager.XTEntityDescriptorType.TUPLE
            or ref_type is XTEntityDescriptorManager.XTEntityDescriptorType.SET
        ):
            content_type = XTEntityDescriptorManager._get_param_type(
                category_content[0]
            )
            for descriptor in category_content:
                match content_type:
                    case XTEntityDescriptorManager.XTEntityDescriptorType.ENTITY:
                        entity = cast(EntityDescription, descriptor)
                        compound_key: str | None = (
                            XTEntityDescriptorManager.get_compound_key(
                                entity, key_fields
                            )
                        )
                        if compound_key is not None:
                            return_list.append(compound_key)
                    case XTEntityDescriptorManager.XTEntityDescriptorType.STRING:
                        return_list.append(descriptor)
        elif ref_type is XTEntityDescriptorManager.XTEntityDescriptorType.DICT:
            for category_key in category_content:
                return_list.append(category_key)
        return return_list

    @staticmethod
    def get_category_dict(
        category_content: Any, key_fields: list[str] = ["key"]
    ) -> dict[str, EntityDescription | None]:
        return_dict: dict[str, EntityDescription | None] = {}
        if not category_content:
            return return_dict
        ref_type = XTEntityDescriptorManager._get_param_type(category_content)
        if (
            ref_type is XTEntityDescriptorManager.XTEntityDescriptorType.LIST
            or ref_type is XTEntityDescriptorManager.XTEntityDescriptorType.TUPLE
            or ref_type is XTEntityDescriptorManager.XTEntityDescriptorType.SET
        ):
            content_type = XTEntityDescriptorManager._get_param_type(
                category_content[0]
            )
            for descriptor in category_content:
                match content_type:
                    case XTEntityDescriptorManager.XTEntityDescriptorType.ENTITY:
                        entity = cast(EntityDescription, descriptor)
                        compound_key: str | None = (
                            XTEntityDescriptorManager.get_compound_key(
                                entity, key_fields
                            )
                        )
                        if compound_key is not None:
                            return_dict[compound_key] = entity
                    case XTEntityDescriptorManager.XTEntityDescriptorType.STRING:
                        return_dict[descriptor] = None
        elif ref_type is XTEntityDescriptorManager.XTEntityDescriptorType.DICT:
            for category_key in category_content:
                return_dict[category_key] = None
        return return_dict

    @staticmethod
    def get_compound_key(
        entity: EntityDescription, key_fields: list[str]
    ) -> str | None:
        compound_key: str | None = None
        for key in key_fields:
            if hasattr(entity, key):
                key_part = getattr(entity, key)
                if key_part is not None:
                    if compound_key is None:
                        compound_key = str(key_part)
                    else:
                        compound_key = f"{compound_key}|{key_part}"
        return compound_key

    @staticmethod
    def get_empty_descriptor(reference_descriptor: Any) -> Any:
        ref_type = XTEntityDescriptorManager._get_param_type(reference_descriptor)
        match ref_type:
            case XTEntityDescriptorManager.XTEntityDescriptorType.DICT:
                return {}
            case XTEntityDescriptorManager.XTEntityDescriptorType.LIST:
                return []
            case XTEntityDescriptorManager.XTEntityDescriptorType.TUPLE:
                return tuple()
            case XTEntityDescriptorManager.XTEntityDescriptorType.STRING:
                return ""
            case XTEntityDescriptorManager.XTEntityDescriptorType.SET:
                return set()
            case _:
                return None

    @staticmethod
    def merge_descriptors(
        base_descriptors: Any,
        descriptors_to_add: Any,
        key_fields: list[str],
        entity_type: type[Any] | None,
    ) -> Any:
        descr1_type = XTEntityDescriptorManager._get_param_type(base_descriptors)
        descr2_type = XTEntityDescriptorManager._get_param_type(descriptors_to_add)
        if (
            descr1_type != descr2_type
            or descr1_type == XTEntityDescriptorManager.XTEntityDescriptorType.UNKNOWN
        ):
            LOGGER.warning(
                f"Merging of descriptors failed, non-matching include/exclude {descr1_type} VS {descr2_type}",
                stack_info=True,
            )
            return base_descriptors
        match descr1_type:
            case XTEntityDescriptorManager.XTEntityDescriptorType.DICT:
                return_dict: dict[str, Any] = {}
                base_cross = None
                add_cross = None
                cross_both = None
                if CROSS_CATEGORY_DEVICE_DESCRIPTOR in base_descriptors:
                    base_cross = base_descriptors[CROSS_CATEGORY_DEVICE_DESCRIPTOR]
                if CROSS_CATEGORY_DEVICE_DESCRIPTOR in descriptors_to_add:
                    add_cross = descriptors_to_add[CROSS_CATEGORY_DEVICE_DESCRIPTOR]
                if base_cross is not None and add_cross is not None:
                    cross_both = XTEntityDescriptorManager.merge_descriptors(
                        base_cross, add_cross, key_fields, entity_type
                    )
                elif base_cross is not None:
                    cross_both = base_cross
                elif add_cross is not None:
                    cross_both = add_cross
                for key in base_descriptors:
                    merged_descriptors = base_descriptors[key]
                    if key in descriptors_to_add:
                        merged_descriptors = (
                            XTEntityDescriptorManager.merge_descriptors(
                                merged_descriptors,
                                descriptors_to_add[key],
                                key_fields,
                                entity_type,
                            )
                        )
                    if cross_both is not None:
                        merged_descriptors = (
                            XTEntityDescriptorManager.merge_descriptors(
                                merged_descriptors, cross_both, key_fields, entity_type
                            )
                        )
                    return_dict[key] = merged_descriptors
                for key in descriptors_to_add:
                    if key not in base_descriptors:
                        merged_descriptors = descriptors_to_add[key]
                        if cross_both is not None:
                            merged_descriptors = (
                                XTEntityDescriptorManager.merge_descriptors(
                                    merged_descriptors,
                                    cross_both,
                                    key_fields,
                                    entity_type,
                                )
                            )
                        return_dict[key] = merged_descriptors
                return return_dict
            case XTEntityDescriptorManager.XTEntityDescriptorType.LIST:
                return_list: list = []
                var_type = XTEntityDescriptorManager.XTEntityDescriptorType.UNKNOWN
                added_compound_keys: list[str] = []
                if descriptors_to_add:
                    var_type = XTEntityDescriptorManager._get_param_type(
                        descriptors_to_add[0]
                    )
                base_descr_keys: dict[str, EntityDescription | None] = (
                    XTEntityDescriptorManager.get_category_dict(
                        base_descriptors, key_fields
                    )
                )
                for descriptor in descriptors_to_add:
                    match var_type:
                        case XTEntityDescriptorManager.XTEntityDescriptorType.ENTITY:
                            entity_to_add = cast(EntityDescription, descriptor)
                            compound_key = XTEntityDescriptorManager.get_compound_key(
                                entity_to_add, key_fields
                            )
                            if compound_key is None:
                                continue
                            if compound_key not in base_descr_keys:
                                return_list.append(entity_to_add)
                                added_compound_keys.append(compound_key)
                            else:
                                if base_entity := base_descr_keys[compound_key]:
                                    added_compound_keys.append(compound_key)
                                    return_list.append(
                                        XTEntityDescriptorManager.merge_descriptor(
                                            base_entity, entity_to_add, entity_type
                                        )
                                    )

                        case XTEntityDescriptorManager.XTEntityDescriptorType.STRING:
                            if descriptor not in base_descr_keys:
                                return_list.append(descriptor)
                for compound_key, base_descriptor in base_descr_keys.items():
                    match var_type:
                        case XTEntityDescriptorManager.XTEntityDescriptorType.ENTITY:
                            if compound_key not in added_compound_keys:
                                return_list.append(base_descriptor)
                        case XTEntityDescriptorManager.XTEntityDescriptorType.STRING:
                            return_list.append(compound_key)
                return return_list
            case XTEntityDescriptorManager.XTEntityDescriptorType.TUPLE:
                return tuple(
                    XTEntityDescriptorManager.merge_descriptors(
                        list(base_descriptors),
                        list(descriptors_to_add),
                        key_fields,
                        entity_type,
                    )
                )
            case XTEntityDescriptorManager.XTEntityDescriptorType.SET:
                return set(
                    XTEntityDescriptorManager.merge_descriptors(
                        list(base_descriptors),
                        list(descriptors_to_add),
                        key_fields,
                        entity_type,
                    )
                )

    @staticmethod
    def merge_descriptor(
        base: EntityDescription, other: EntityDescription, real_type: type[Any] | None
    ) -> EntityDescription:
        if real_type is None:
            return base
        base_dict = base.__dict__
        if (
            other.translation_placeholders is not None
            and base.translation_placeholders is None
        ):
            base_dict["translation_key"] = other.translation_key
            base_dict["translation_placeholders"] = other.translation_placeholders
        return real_type(**base_dict)

    @staticmethod
    def exclude_descriptors(base_descriptors: Any, exclude_descriptors: Any) -> Any:
        base_type = XTEntityDescriptorManager._get_param_type(base_descriptors)
        exclude_type = XTEntityDescriptorManager._get_param_type(exclude_descriptors)
        if (
            base_type != exclude_type
            or base_type == XTEntityDescriptorManager.XTEntityDescriptorType.UNKNOWN
        ):
            LOGGER.warning(
                f"Merging of descriptors failed, non-matching include/exclude {base_type} VS {exclude_type}",
                stack_info=True,
            )
            return base_descriptors
        match base_type:
            case XTEntityDescriptorManager.XTEntityDescriptorType.DICT:
                return_dict: dict[str, Any] = {}
                for key in base_descriptors:
                    if key in exclude_descriptors:
                        exclude_result = XTEntityDescriptorManager.exclude_descriptors(
                            base_descriptors[key], exclude_descriptors[key]
                        )
                        if exclude_result:
                            return_dict[key] = exclude_result
                    else:
                        return_dict[key] = base_descriptors[key]
                return return_dict
            case XTEntityDescriptorManager.XTEntityDescriptorType.LIST:
                return_list: list = []
                exclude_keys: list[str] = []
                var_type = XTEntityDescriptorManager.XTEntityDescriptorType.UNKNOWN
                if base_descriptors:
                    var_type = XTEntityDescriptorManager._get_param_type(
                        base_descriptors[0]
                    )
                for descriptor in exclude_descriptors:
                    match var_type:
                        case XTEntityDescriptorManager.XTEntityDescriptorType.ENTITY:
                            entity = cast(EntityDescription, descriptor)
                            exclude_keys.append(entity.key)
                        case XTEntityDescriptorManager.XTEntityDescriptorType.STRING:
                            exclude_keys.append(descriptor)
                for descriptor in base_descriptors:
                    match var_type:
                        case XTEntityDescriptorManager.XTEntityDescriptorType.ENTITY:
                            entity = cast(EntityDescription, descriptor)
                            if entity.key not in exclude_keys:
                                return_list.append(descriptor)
                        case XTEntityDescriptorManager.XTEntityDescriptorType.STRING:
                            if descriptor not in exclude_keys:
                                return_list.append(descriptor)
                return return_list
            case XTEntityDescriptorManager.XTEntityDescriptorType.TUPLE:
                return tuple(
                    XTEntityDescriptorManager.exclude_descriptors(
                        list(base_descriptors), list(exclude_descriptors)
                    )
                )
            case XTEntityDescriptorManager.XTEntityDescriptorType.SET:
                return set(
                    XTEntityDescriptorManager.exclude_descriptors(
                        list(base_descriptors), list(exclude_descriptors)
                    )
                )

    @staticmethod
    def _get_param_type(param) -> XTEntityDescriptorManager.XTEntityDescriptorType:
        if param is None:
            LOGGER.warning(
                "_get_param_type is returning UNKNOWN because of None input",
                stack_info=True,
            )
            return XTEntityDescriptorManager.XTEntityDescriptorType.UNKNOWN
        elif isinstance(param, dict):
            return XTEntityDescriptorManager.XTEntityDescriptorType.DICT
        elif isinstance(param, list):
            return XTEntityDescriptorManager.XTEntityDescriptorType.LIST
        elif isinstance(param, tuple):
            return XTEntityDescriptorManager.XTEntityDescriptorType.TUPLE
        elif isinstance(param, set):
            return XTEntityDescriptorManager.XTEntityDescriptorType.SET
        elif isinstance(param, str):
            return XTEntityDescriptorManager.XTEntityDescriptorType.STRING
        elif isinstance(param, XTEntityDescriptorManager.entity_type):
            return XTEntityDescriptorManager.XTEntityDescriptorType.ENTITY
        else:
            LOGGER.warning(
                f"Type {type(param)} is not handled in _get_param_type (bases: {type(param).__mro__}) check: {XTEntityDescriptorManager.entity_type}"
            )
            return XTEntityDescriptorManager.XTEntityDescriptorType.UNKNOWN


class XTEntity(TuyaEntity):
    class XTEntityAccessMode(StrEnum):
        READ_ONLY = "ro"
        READ_WRITE = "rw"
        WRITE_ONLY = "wr"

    def __init__(self, *args, **kwargs) -> None:
        # This is to catch the super call in case the next class in parent's MRO doesn't have an init method
        try:
            super().__init__(*args, **kwargs)
        except Exception:
            # In case we have an error, do nothing
            pass

    @overload
    def find_dpcode(
        self,
        dpcodes: (
            str
            | XTDPCode
            | tuple[XTDPCode, ...]
            | TuyaDPCode
            | tuple[TuyaDPCode, ...]
            | None
        ),
        *,
        prefer_function: bool = False,
        dptype: Literal[TuyaDPType.ENUM],
        only_function: bool = False,
    ) -> TuyaEnumTypeData | None: ...

    @overload
    def find_dpcode(
        self,
        dpcodes: (
            str
            | XTDPCode
            | tuple[XTDPCode, ...]
            | TuyaDPCode
            | tuple[TuyaDPCode, ...]
            | None
        ),
        *,
        prefer_function: bool = False,
        dptype: Literal[TuyaDPType.INTEGER],
        only_function: bool = False,
    ) -> TuyaIntegerTypeData | None: ...

    @overload
    def find_dpcode(
        self,
        dpcodes: (
            str
            | XTDPCode
            | tuple[XTDPCode, ...]
            | TuyaDPCode
            | tuple[TuyaDPCode, ...]
            | None
        ),
        *,
        prefer_function: bool = False,
        only_function: bool = False,
    ) -> TuyaDPCode | None: ...

    @overload
    def find_dpcode(
        self,
        dpcodes: (
            str
            | XTDPCode
            | tuple[XTDPCode, ...]
            | TuyaDPCode
            | tuple[TuyaDPCode, ...]
            | None
        ),
        *,
        prefer_function: bool = False,
        dptype: TuyaDPType | None = None,
        only_function: bool = False,
    ) -> TuyaDPCode | TuyaEnumTypeData | TuyaIntegerTypeData | None: ...

    def find_dpcode(
        self,
        dpcodes: (
            str
            | XTDPCode
            | tuple[XTDPCode, ...]
            | TuyaDPCode
            | tuple[TuyaDPCode, ...]
            | None
        ),
        *,
        prefer_function: bool = False,
        dptype: TuyaDPType | None = None,
        only_function: bool = False,
    ) -> str | XTDPCode | TuyaDPCode | TuyaEnumTypeData | TuyaIntegerTypeData | None:
        if only_function:
            return self._find_dpcode(
                dpcodes=dpcodes,
                prefer_function=prefer_function,
                dptype=dptype,
                only_function=only_function,
            )
        try:
            if dpcodes is None:
                return None
            elif not isinstance(dpcodes, tuple):
                dpcodes = (TuyaDPCode(dpcodes),)
            else:
                dpcodes = (TuyaDPCode(dpcodes),)
            if dptype is TuyaDPType.ENUM:
                return super(XTEntity, self).find_dpcode(
                    dpcodes=dpcodes, prefer_function=prefer_function, dptype=dptype
                )
            elif dptype is TuyaDPType.INTEGER:
                return super(XTEntity, self).find_dpcode(
                    dpcodes=dpcodes, prefer_function=prefer_function, dptype=dptype
                )
            else:
                return dpcodes[0]
        except Exception:
            """Find a matching DP code available on for this device."""
            return self._find_dpcode(
                dpcodes=dpcodes,
                prefer_function=prefer_function,
                dptype=dptype,
                only_function=only_function,
            )

    def _find_dpcode(
        self,
        dpcodes: (
            str
            | tuple[str, ...]
            | XTDPCode
            | tuple[XTDPCode, ...]
            | TuyaDPCode
            | tuple[TuyaDPCode, ...]
            | None
        ),
        *,
        prefer_function: bool = False,
        dptype: TuyaDPType | None = None,
        only_function: bool = False,
    ) -> str | XTDPCode | TuyaDPCode | TuyaEnumTypeData | TuyaIntegerTypeData | None:
        if dpcodes is None:
            return None

        if not isinstance(dpcodes, tuple):
            dpcodes = (dpcodes,)

        order = ["status_range", "function"]
        if prefer_function:
            order = ["function", "status_range"]
        if only_function:
            order = ["function"]

        # When we are not looking for a specific datatype, we can append status for
        # searching
        if not dptype:
            order.append("status")

        for dpcode in dpcodes:
            for key in order:
                if dpcode not in getattr(self.device, key):
                    continue
                if (
                    dptype == TuyaDPType.ENUM
                    and getattr(self.device, key)[dpcode].type == TuyaDPType.ENUM
                ):
                    if not (
                        enum_type := TuyaEnumTypeData.from_json(
                            dpcode,  # type: ignore
                            getattr(self.device, key)[dpcode].values,
                        )
                    ):
                        continue
                    return enum_type

                if (
                    dptype == TuyaDPType.INTEGER
                    and getattr(self.device, key)[dpcode].type == TuyaDPType.INTEGER
                ):
                    if not (
                        integer_type := TuyaIntegerTypeData.from_json(
                            dpcode,  # type: ignore
                            getattr(self.device, key)[dpcode].values,
                        )
                    ):
                        continue
                    return integer_type

                if dptype not in (TuyaDPType.ENUM, TuyaDPType.INTEGER):
                    return dpcode

        return None

    def get_dptype(
        self,
        dpcode: XTDPCode | TuyaDPCode | None,
        device: sc.XTDevice | None = None,
        *,
        prefer_function: bool = False,
    ) -> TuyaDPType | None:
        """Find a matching DPType type information for this device DPCode."""
        if dpcode is None:
            return None
        if device is None:
            return self.get_dptype_old(dpcode, prefer_function=prefer_function)
        lookup_tuple = (
            (device.function, device.status_range)
            if prefer_function
            else (device.status_range, device.function)
        )
        for device_specs in lookup_tuple:
            if current_definition := device_specs.get(dpcode):
                current_type = current_definition.type
                if current_type is not None:
                    try:
                        return TuyaDPType(current_type)
                    except ValueError:
                        # Sometimes, we get ill-formed DPTypes from the cloud,
                        # this fixes them and maps them to the correct DPType.
                        return TUYA_DPTYPE_MAPPING.get(current_type)
        return None
    
    def get_dptype_old(
        self, dpcode: XTDPCode | TuyaDPCode | None, *, prefer_function: bool = False
    ) -> TuyaDPType | None:
        """Find a matching DPCode data type available on for this device."""
        if dpcode is None:
            return None

        order = ["status_range", "function"]
        if prefer_function:
            order = ["function", "status_range"]
        for key in order:
            if dpcode in getattr(self.device, key):
                current_type = getattr(self.device, key)[dpcode].type
                try:
                    return TuyaDPType(current_type)
                except ValueError:
                    # Sometimes, we get ill-formed DPTypes from the cloud,
                    # this fixes them and maps them to the correct DPType.
                    return TUYA_DPTYPE_MAPPING.get(current_type)

        return None

    @staticmethod
    def determine_dptype(type) -> TuyaDPType | None:
        """Determine the DPType.

        Sometimes, we get ill-formed DPTypes from the cloud,
        this fixes them and maps them to the correct DPType.
        """
        try:
            return TuyaDPType(type)
        except ValueError:
            return TUYA_DPTYPE_MAPPING.get(type)

    @staticmethod
    def mark_overriden_entities_as_disables(hass: HomeAssistant, device: sc.XTDevice):
        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)
        hass_device = device_registry.async_get_device(
            identifiers={(DOMAIN, device.id), (DOMAIN_ORIG, device.id)}
        )
        entity_platforms = async_get_platforms(hass, DOMAIN_ORIG)
        if hass_device:
            hass_entities = er.async_entries_for_device(
                entity_registry,
                device_id=hass_device.id,
                include_disabled_entities=False,
            )
            for entity_registration in hass_entities:
                for entity_platform in entity_platforms:
                    if entity_registration.entity_id in entity_platform.entities:
                        entity_instance_platform = Platform(entity_platform.domain)
                        if entity_instance_platform in FULLY_OVERRIDEN_PLATFORMS:
                            entity_registry.async_update_entity(
                                entity_id=entity_registration.entity_id,
                                disabled_by=RegistryEntryDisabler.USER,
                            )

    @staticmethod
    def register_current_entities_as_handled_dpcode(
        hass: HomeAssistant, device: sc.XTDevice
    ):
        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)
        hass_device = device_registry.async_get_device(
            identifiers={(DOMAIN, device.id), (DOMAIN_ORIG, device.id)}
        )
        entity_platforms = async_get_platforms(hass, DOMAIN_ORIG)
        if hass_device:
            hass_entities = er.async_entries_for_device(
                entity_registry,
                device_id=hass_device.id,
                include_disabled_entities=False,
            )
            for entity_registration in hass_entities:
                for entity_platform in entity_platforms:
                    if entity_registration.entity_id in entity_platform.entities:
                        entity_instance = entity_platform.entities[
                            entity_registration.entity_id
                        ]
                        entity_instance_platform = Platform(entity_platform.domain)
                        entity_description: EntityDescription | None = None
                        if hasattr(entity_instance, "entity_description"):
                            entity_description = entity_instance.entity_description
                        if entity_description is not None:
                            dpcode = XTEntity._get_description_dpcode(
                                entity_description
                            )
                            XTEntity.register_handled_dpcode(
                                device, entity_instance_platform, dpcode
                            )
                            if hasattr(entity_description, "subkey"):
                                compound_key = (
                                    XTEntityDescriptorManager.get_compound_key(
                                        entity_description, ["key", "subkey"]
                                    )
                                )
                                if compound_key is not None:
                                    XTEntity.register_handled_dpcode(
                                        device, entity_instance_platform, compound_key
                                    )

    @staticmethod
    def register_handled_dpcode(device: sc.XTDevice, platform: Platform, dpcode: str):
        handled_dpcodes: dict[str, list[str]] = cast(
            dict[str, list[str]],
            device.get_preference(sc.XTDevice.XTDevicePreference.HANDLED_DPCODES, {}),
        )
        if platform not in handled_dpcodes:
            handled_dpcodes[platform] = []
        if dpcode not in handled_dpcodes[platform]:
            handled_dpcodes[platform].append(dpcode)
        device.set_preference(
            sc.XTDevice.XTDevicePreference.HANDLED_DPCODES, handled_dpcodes
        )

    @staticmethod
    def is_dpcode_handled(device: sc.XTDevice, platform: Platform, dpcode: str) -> bool:
        handled_dpcodes: dict[str, list[str]] = cast(
            dict[str, list[str]],
            device.get_preference(sc.XTDevice.XTDevicePreference.HANDLED_DPCODES, {}),
        )
        if platform not in handled_dpcodes:
            return False
        if dpcode in handled_dpcodes[platform]:
            return True
        return False

    @staticmethod
    def supports_description(
        device: sc.XTDevice,
        platform: Platform,
        description: EntityDescription,
        first_pass: bool,
        externally_managed_dpcodes: list[str] = [],
        key_fields: list[str] | None = None,
        multi_manager: mm.MultiManager | None = None
    ) -> bool:
        result, dpcode = XTEntity._supports_description(
            device,
            platform,
            description,
            first_pass,
            externally_managed_dpcodes,
            key_fields,
        )
        if multi_manager is not None and description.key == XTDPCode.ADD_ELE:
            multi_manager.device_watcher.report_message(device.id, f"ADD ELE support: {result}, dpcode: {dpcode}, externally manager: {externally_managed_dpcodes}")
        if result is True:
            # Register the code as being handled by the device
            XTEntity.register_handled_dpcode(device, platform, dpcode)
            if key_fields is not None:
                compound_key = XTEntityDescriptorManager.get_compound_key(
                    description, key_fields
                )
                if compound_key is not None:
                    XTEntity.register_handled_dpcode(device, platform, compound_key)
        return result

    @staticmethod
    def _get_description_dpcode(description: EntityDescription) -> str:
        import custom_components.xtend_tuya.binary_sensor as XTBinarySensor

        dpcode = description.key
        if isinstance(description, XTBinarySensor.XTBinarySensorEntityDescription):
            if dpcode is None and description.dpcode is not None:
                dpcode = description.dpcode
        return dpcode

    @staticmethod
    def _supports_description(
        device: sc.XTDevice,
        platform: Platform,
        description: EntityDescription,
        first_pass: bool,
        externally_managed_dpcodes: list[str],
        key_fields: list[str] | None = None,
    ) -> tuple[bool, str]:
        dpcode = XTEntity._get_description_dpcode(description)
        compound_key = None
        if key_fields is not None:
            compound_key = XTEntityDescriptorManager.get_compound_key(
                description, key_fields
            )
        if XTEntity.is_dpcode_handled(device, platform, dpcode) is True:
            if (
                compound_key is None
                or XTEntity.is_dpcode_handled(device, platform, compound_key) is True
            ):
                return False, dpcode
        if first_pass is True:
            if dpcode in device.status:
                return True, dpcode
            return False, dpcode
        else:
            # if device.force_compatibility is True:
            #    return False, dpcode

            all_aliases = device.get_all_status_code_aliases()
            if current_status := all_aliases.get(dpcode):
                if (
                    XTEntity.is_dpcode_handled(device, platform, current_status)
                    is False
                ):
                    device.replace_status_code_with_another(current_status, dpcode)
                    return True, dpcode
        return False, dpcode

    @staticmethod
    def __is_dpcode_suitable_for_platform(
        device: sc.XTDevice, dpcode: str, platform: Platform
    ) -> bool:
        dpcode_info = device.get_dpcode_information(dpcode=dpcode)
        if (
            dpcode_info is None
            or dpcode_info.dptype is None
            or dpcode_info.dpid
            is None  # DPcodes added as virtual dpcodes have a DPID = 0
        ):
            return False
        match platform:
            case Platform.BINARY_SENSOR:
                if dpcode_info.dptype not in [TuyaDPType.BOOLEAN, TuyaDPType.BITMAP]:
                    return False
                if dpcode_info.read_only is True:
                    return True
            case Platform.SENSOR:
                if dpcode_info.dptype not in [
                    TuyaDPType.ENUM,
                    TuyaDPType.INTEGER,
                    TuyaDPType.STRING,
                ]:
                    return False
                if dpcode_info.read_only is True:
                    return True
            case Platform.NUMBER:
                if dpcode_info.dptype not in [TuyaDPType.INTEGER]:
                    return False
                if (
                    dpcode_info.read_write is True
                    and dpcode_info.min is not None
                    and dpcode_info.max is not None
                    and dpcode_info.scale is not None
                    and dpcode_info.step is not None
                ):
                    return True
            case Platform.SELECT:
                if dpcode_info.dptype not in [TuyaDPType.ENUM]:
                    return False
                if dpcode_info.read_write is True:
                    return True
            case Platform.LIGHT:
                if dpcode_info.dptype not in [TuyaDPType.JSON, TuyaDPType.RAW]:
                    return False
                if (
                    dpcode_info.read_write is True
                    and dpcode_info.value_descr_dict.get("h") is not None
                    and dpcode_info.value_descr_dict.get("s") is not None
                    and dpcode_info.value_descr_dict.get("v") is not None
                ):
                    return True
            case Platform.SWITCH:
                if dpcode_info.dptype not in [TuyaDPType.BOOLEAN]:
                    return False
                if dpcode_info.read_write is True:
                    return True
        return False

    @staticmethod
    def get_generic_dpcodes_for_this_platform(
        device: sc.XTDevice, platform: Platform
    ) -> list[str]:
        return_list: list[str] = []
        for dpcode in device.status:
            # Don't add already handled DPCodes
            if XTEntity.is_dpcode_handled(device, platform, dpcode) is True:
                continue

            # Filter DPCodes that are not for the current platform
            if (
                XTEntity.__is_dpcode_suitable_for_platform(device, dpcode, platform)
                is False
            ):
                continue
            return_list.append(dpcode)
        return return_list

    @staticmethod
    def get_human_name(technical_name: str) -> str:
        human_name = technical_name
        human_name = human_name.replace("_", " ")
        human_name = human_name.capitalize()
        return human_name
