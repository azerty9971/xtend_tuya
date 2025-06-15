from __future__ import annotations

from typing import overload, Literal
from dataclasses import dataclass

from .const import (
    XTDPCode,
    DPType,
    LOGGER,
)

from .multi_manager.multi_manager import (
    MultiManager,
)

from .ha_tuya_integration.tuya_integration_imports import (
    TuyaEnumTypeData,
    TuyaIntegerTypeData,
    TUYA_DPTYPE_MAPPING,
    TuyaEntity,
    TuyaDPCode,
)

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
        dptype: Literal[DPType.ENUM],
    ) -> TuyaEnumTypeData | None: ...

    @overload
    def find_dpcode(
        self,
        dpcodes: str | XTDPCode | tuple[XTDPCode, ...] | TuyaDPCode | tuple[TuyaDPCode, ...] | None,
        *,
        prefer_function: bool = False,
        dptype: Literal[DPType.INTEGER],
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
        dptype: DPType | None = None,
    ) -> TuyaDPCode | TuyaEnumTypeData | TuyaIntegerTypeData | None: ...
        
    def find_dpcode(
        self,
        dpcodes: str | XTDPCode | tuple[XTDPCode, ...] | TuyaDPCode | tuple[TuyaDPCode, ...] | None,
        *,
        prefer_function: bool = False,
        dptype: DPType | None = None,
    ) -> XTDPCode | TuyaDPCode | TuyaEnumTypeData | TuyaIntegerTypeData | None:
        try:
            if dpcodes is None:
                return None
            elif not isinstance(dpcodes, tuple):
                dpcodes = (TuyaDPCode(dpcodes),)
            else:
                dpcodes = (TuyaDPCode(dpcodes),)
            if dptype is DPType.ENUM:
                return super(XTEntity, self).find_dpcode(dpcodes=dpcodes, prefer_function=prefer_function, dptype=dptype)
            elif dptype is DPType.INTEGER:
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
                        dptype == DPType.ENUM
                        and getattr(self.device, key)[dpcode].type == DPType.ENUM
                    ):
                        if not (
                            enum_type := TuyaEnumTypeData.from_json(
                                dpcode, getattr(self.device, key)[dpcode].values # type: ignore
                            )
                        ):
                            continue
                        return enum_type

                    if (
                        dptype == DPType.INTEGER
                        and getattr(self.device, key)[dpcode].type == DPType.INTEGER
                    ):
                        if not (
                            integer_type := TuyaIntegerTypeData.from_json(
                                dpcode, getattr(self.device, key)[dpcode].values # type: ignore
                            )
                        ):
                            continue
                        return integer_type

                    if dptype not in (DPType.ENUM, DPType.INTEGER):
                        return dpcode

            return None
    
    @staticmethod
    def determine_dptype(type) -> DPType | None:
        """Determine the DPType.

        Sometimes, we get ill-formed DPTypes from the cloud,
        this fixes them and maps them to the correct DPType.
        """
        try:
            return DPType(type)
        except ValueError:
            return TUYA_DPTYPE_MAPPING.get(type)