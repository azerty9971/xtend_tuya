from __future__ import annotations

from typing import overload, Literal, cast

from homeassistant.helpers.entity import EntityDescription

from .const import (
    XTDPCode,
    LOGGER,  # noqa: F401
)

from .multi_manager.shared.shared_classes import (
    XTDevice,
)

from .ha_tuya_integration.tuya_integration_imports import (
    TuyaEnumTypeData,
    TuyaIntegerTypeData,
    TUYA_DPTYPE_MAPPING,
    TuyaEntity,
    TuyaDPCode,
    TuyaDPType,
)

import custom_components.xtend_tuya.binary_sensor as XTBinarySensor

class XTEntity(TuyaEntity):
    def __init__(
        self,
        *args,
        **kwargs
    ) -> None:
        #This is to catch the super call in case the next class in parent's MRO doesn't have an init method
        try:
            super().__init__(*args, **kwargs)
        except Exception:
            #In case we have an error, do nothing
            pass

    @overload
    def find_dpcode(
        self,
        dpcodes: str | XTDPCode | tuple[XTDPCode, ...] | TuyaDPCode | tuple[TuyaDPCode, ...] | None,
        *,
        prefer_function: bool = False,
        dptype: Literal[TuyaDPType.ENUM],
    ) -> TuyaEnumTypeData | None: ...

    @overload
    def find_dpcode(
        self,
        dpcodes: str | XTDPCode | tuple[XTDPCode, ...] | TuyaDPCode | tuple[TuyaDPCode, ...] | None,
        *,
        prefer_function: bool = False,
        dptype: Literal[TuyaDPType.INTEGER],
    ) -> TuyaIntegerTypeData | None: ...

    @overload
    def find_dpcode(
        self,
        dpcodes: str | XTDPCode | tuple[XTDPCode, ...] | TuyaDPCode | tuple[TuyaDPCode, ...] | None,
        *,
        prefer_function: bool = False,
    ) -> TuyaDPCode | None: ...

    @overload
    def find_dpcode(
        self,
        dpcodes: str | XTDPCode | tuple[XTDPCode, ...] | TuyaDPCode | tuple[TuyaDPCode, ...] | None,
        *,
        prefer_function: bool = False,
        dptype: TuyaDPType | None = None,
    ) -> TuyaDPCode | TuyaEnumTypeData | TuyaIntegerTypeData | None: ...
        
    def find_dpcode(
        self,
        dpcodes: str | XTDPCode | tuple[XTDPCode, ...] | TuyaDPCode | tuple[TuyaDPCode, ...] | None,
        *,
        prefer_function: bool = False,
        dptype: TuyaDPType | None = None,
    ) -> XTDPCode | TuyaDPCode | TuyaEnumTypeData | TuyaIntegerTypeData | None:
        try:
            if dpcodes is None:
                return None
            elif not isinstance(dpcodes, tuple):
                dpcodes = (TuyaDPCode(dpcodes),)
            else:
                dpcodes = (TuyaDPCode(dpcodes),)
            if dptype is TuyaDPType.ENUM:
                return super(XTEntity, self).find_dpcode(dpcodes=dpcodes, prefer_function=prefer_function, dptype=dptype)
            elif dptype is TuyaDPType.INTEGER:
                return super(XTEntity, self).find_dpcode(dpcodes=dpcodes, prefer_function=prefer_function, dptype=dptype)
            else:
                return dpcodes[0]
        except Exception:
            """Find a matching DP code available on for this device."""
            if dpcodes is None:
                return None

            if isinstance(dpcodes, str):
                dpcodes = (XTDPCode(dpcodes),)
            elif not isinstance(dpcodes, tuple):
                dpcodes = (dpcodes,)

            order = ["status_range", "function"]
            if prefer_function:
                order = ["function", "status_range"]

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
                                dpcode, getattr(self.device, key)[dpcode].values # type: ignore
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
                                dpcode, getattr(self.device, key)[dpcode].values # type: ignore
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
    def supports_description(device: XTDevice, description: EntityDescription, first_pass: bool) -> bool:
        result, dpcode = XTEntity._supports_description(device, description, first_pass)
        if result is True:
            #Register the code as being handled by the device
            handled_dpcodes: list[str] = cast(list[str], device.get_preference(XTDevice.XTDevicePreference.HANDLED_DPCODES, []))
            if dpcode not in handled_dpcodes:
                handled_dpcodes.append(dpcode)
                device.set_preference(XTDevice.XTDevicePreference.HANDLED_DPCODES, handled_dpcodes)
        return result

    @staticmethod
    def _supports_description(device: XTDevice, description: EntityDescription, first_pass: bool) -> tuple[bool, str]:
        dpcode = description.key
        if isinstance(description, XTBinarySensor.XTBinarySensorEntityDescription):
            if description.dpcode is not None:
                dpcode = description.dpcode
        if first_pass is True:
            if dpcode in device.status:
                return True, dpcode
            return False, dpcode
        else:
            if device.force_compatibility is True:
                return False, dpcode

            all_aliases = device.get_all_status_code_aliases()
            if current_status := all_aliases.get(dpcode):
                handled_dpcodes: list[str] = cast(list[str], device.get_preference(XTDevice.XTDevicePreference.HANDLED_DPCODES, []))
                if current_status not in handled_dpcodes:
                    device.replace_status_with_another(current_status, dpcode)
                    return True, dpcode
        return False, dpcode