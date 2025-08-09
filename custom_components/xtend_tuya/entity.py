from __future__ import annotations
from typing import overload, Literal, cast, Any
from enum import StrEnum
from homeassistant.helpers.entity import EntityDescription
from homeassistant.const import Platform
from .const import (
    XTDPCode,
    LOGGER,  # noqa: F401
    CROSS_CATEGORY_DEVICE_DESCRIPTOR,
)
from .multi_manager.shared.shared_classes import (
    XTDevice,
)
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
        platform_descriptors: Any, multi_manager: mm.MultiManager, platform: Platform | None
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
                    include_descriptors, descriptors_to_add
                )
            for descriptors_to_exclude in multi_manager.get_platform_descriptors_to_exclude(
                platform
            ):
                exclude_descriptors = XTEntityDescriptorManager.merge_descriptors(
                    exclude_descriptors, descriptors_to_exclude
                )
        include_descriptors = XTEntityDescriptorManager.exclude_descriptors(
            include_descriptors, exclude_descriptors
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
    def get_category_keys(category_content: Any) -> list[str]:
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
                        return_list.append(entity.key)
                    case XTEntityDescriptorManager.XTEntityDescriptorType.STRING:
                        return_list.append(descriptor)
        elif ref_type is XTEntityDescriptorManager.XTEntityDescriptorType.DICT:
            for category_key in category_content:
                return_list.append(category_key)
        return return_list

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
    def merge_descriptors(descriptors1: Any, descriptors2: Any) -> Any:
        descr1_type = XTEntityDescriptorManager._get_param_type(descriptors1)
        descr2_type = XTEntityDescriptorManager._get_param_type(descriptors2)
        if (
            descr1_type != descr2_type
            or descr1_type == XTEntityDescriptorManager.XTEntityDescriptorType.UNKNOWN
        ):
            LOGGER.warning(
                f"Merging of descriptors failed, non-matching include/exclude {descr1_type} VS {descr2_type}",
                stack_info=True,
            )
            return descriptors1
        match descr1_type:
            case XTEntityDescriptorManager.XTEntityDescriptorType.DICT:
                return_dict: dict[str, Any] = {}
                cross1 = None
                cross2 = None
                cross_both = None
                if CROSS_CATEGORY_DEVICE_DESCRIPTOR in descriptors1:
                    cross1 = descriptors1[CROSS_CATEGORY_DEVICE_DESCRIPTOR]
                if CROSS_CATEGORY_DEVICE_DESCRIPTOR in descriptors2:
                    cross2 = descriptors2[CROSS_CATEGORY_DEVICE_DESCRIPTOR]
                if cross1 is not None and cross2 is not None:
                    cross_both = XTEntityDescriptorManager.merge_descriptors(
                        cross1, cross2
                    )
                elif cross1 is not None:
                    cross_both = cross1
                elif cross2 is not None:
                    cross_both = cross2
                for key in descriptors1:
                    merged_descriptors = descriptors1[key]
                    if key in descriptors2:
                        merged_descriptors = XTEntityDescriptorManager.merge_descriptors(
                            merged_descriptors, descriptors2[key]
                        )
                    if cross_both is not None:
                        merged_descriptors = (
                            XTEntityDescriptorManager.merge_descriptors(
                                merged_descriptors, cross_both
                            )
                        )
                    return_dict[key] = merged_descriptors
                for key in descriptors2:
                    merged_descriptors = descriptors2[key]
                    if cross_both is not None:
                        merged_descriptors = (
                            XTEntityDescriptorManager.merge_descriptors(
                                merged_descriptors, cross_both
                            )
                        )
                    if key not in descriptors1:
                        return_dict[key] = merged_descriptors
                return return_dict
            case XTEntityDescriptorManager.XTEntityDescriptorType.LIST:
                return_list: list = descriptors2
                var_type = XTEntityDescriptorManager.XTEntityDescriptorType.UNKNOWN
                if descriptors1:
                    var_type = XTEntityDescriptorManager._get_param_type(
                        descriptors1[0]
                    )
                descr2_keys: list[str] = XTEntityDescriptorManager.get_category_keys(
                    descriptors2
                )
                for descriptor in descriptors1:
                    match var_type:
                        case XTEntityDescriptorManager.XTEntityDescriptorType.ENTITY:
                            entity = cast(EntityDescription, descriptor)
                            if entity.key not in descr2_keys:
                                return_list.append(descriptor)
                        case XTEntityDescriptorManager.XTEntityDescriptorType.STRING:
                            if descriptor not in descr2_keys:
                                return_list.append(descriptor)
                return return_list
            case XTEntityDescriptorManager.XTEntityDescriptorType.TUPLE:
                return tuple(
                    XTEntityDescriptorManager.merge_descriptors(
                        list(descriptors1), list(descriptors2)
                    )
                )
            case XTEntityDescriptorManager.XTEntityDescriptorType.SET:
                return set(
                    XTEntityDescriptorManager.merge_descriptors(
                        list(descriptors1), list(descriptors2)
                    )
                )

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
                        exclude_result = (
                            XTEntityDescriptorManager.exclude_descriptors(
                                base_descriptors[key], exclude_descriptors[key]
                            )
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
            LOGGER.warning("Returning UNKNOWN for because of None", stack_info=True)
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
            LOGGER.warning(f"Type {type(param)} is not handled in _get_param_type (bases: {type(param).__mro__}) check: {XTEntityDescriptorManager.entity_type}")
            return XTEntityDescriptorManager.XTEntityDescriptorType.UNKNOWN


class XTEntity(TuyaEntity):
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
    ) -> XTDPCode | TuyaDPCode | TuyaEnumTypeData | TuyaIntegerTypeData | None:
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
    ) -> XTDPCode | TuyaDPCode | TuyaEnumTypeData | TuyaIntegerTypeData | None:
        if dpcodes is None:
            return None

        if isinstance(dpcodes, str):
            dpcodes = (XTDPCode(dpcodes),)
        elif not isinstance(dpcodes, tuple):
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
                            dpcode, getattr(self.device, key)[dpcode].values  # type: ignore
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
                            dpcode, getattr(self.device, key)[dpcode].values  # type: ignore
                        )
                    ):
                        continue
                    return integer_type

                if dptype not in (TuyaDPType.ENUM, TuyaDPType.INTEGER):
                    return dpcode

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
    def supports_description(
        device: XTDevice,
        description: EntityDescription,
        first_pass: bool,
        externally_managed_dpcodes: list[str] = [],
    ) -> bool:
        result, dpcode = XTEntity._supports_description(
            device, description, first_pass, externally_managed_dpcodes
        )
        if result is True:
            # Register the code as being handled by the device
            handled_dpcodes: list[str] = cast(
                list[str],
                device.get_preference(XTDevice.XTDevicePreference.HANDLED_DPCODES, []),
            )
            if dpcode not in handled_dpcodes:
                handled_dpcodes.append(dpcode)
                device.set_preference(
                    XTDevice.XTDevicePreference.HANDLED_DPCODES, handled_dpcodes
                )
        return result

    @staticmethod
    def _supports_description(
        device: XTDevice,
        description: EntityDescription,
        first_pass: bool,
        externally_managed_dpcodes: list[str],
    ) -> tuple[bool, str]:
        import custom_components.xtend_tuya.binary_sensor as XTBinarySensor

        dpcode = description.key
        if isinstance(description, XTBinarySensor.XTBinarySensorEntityDescription):
            if description.dpcode is not None:
                dpcode = description.dpcode
        if first_pass is True:
            if dpcode in device.status and dpcode not in externally_managed_dpcodes:
                return True, dpcode
            return False, dpcode
        else:
            # if device.force_compatibility is True:
            #    return False, dpcode

            all_aliases = device.get_all_status_code_aliases()
            if current_status := all_aliases.get(dpcode):
                handled_dpcodes: list[str] = cast(
                    list[str],
                    device.get_preference(
                        XTDevice.XTDevicePreference.HANDLED_DPCODES, []
                    ),
                )
                if (
                    current_status not in handled_dpcodes
                    and current_status not in externally_managed_dpcodes
                ):
                    device.replace_status_with_another(current_status, dpcode)
                    return True, dpcode
        return False, dpcode
