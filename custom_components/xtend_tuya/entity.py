from __future__ import annotations

from .const import (
    XTDPCode,
    DPType,
)

from .multi_manager.shared.device import (
    XTDevice,
)
from .multi_manager.multi_manager import (
    MultiManager,
)

from .ha_tuya_integration.tuya_integration_imports import (
    TuyaEnumTypeData,
    TuyaIntegerTypeData,
    TUYA_DPTYPE_MAPPING,
)

PARAMETER_NOT_ASSIGNED = "!!!PARAMETER IS NOT ASSIGNED!!!"

class XTEntityNotConstructed:
    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: any | None = None,
    ) -> None:
        #This is to catch the super call in case the next class in parent's MRO doesn't have an init method
        pass

class XTEntity(XTEntityNotConstructed):
    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: any = PARAMETER_NOT_ASSIGNED,
    ) -> None:
        """Init XT number."""
        if description is not PARAMETER_NOT_ASSIGNED:
            super(XTEntity, self).__init__(device, device_manager, description)
        else:
            super(XTEntity, self).__init__(device, device_manager)

    def find_dpcode(
        self,
        dpcodes: str | XTDPCode | tuple[XTDPCode, ...] | None,
        *,
        prefer_function: bool = False,
        dptype: DPType | None = None,
    ) -> XTDPCode | TuyaEnumTypeData | TuyaIntegerTypeData | None:
        try:
            return super(XTEntity, self).find_dpcode(dpcodes=dpcodes, prefer_function=prefer_function, dptype=dptype)
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
                                dpcode, getattr(self.device, key)[dpcode].values
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
                                dpcode, getattr(self.device, key)[dpcode].values
                            )
                        ):
                            continue
                        return integer_type

                    if dptype not in (DPType.ENUM, DPType.INTEGER):
                        return dpcode

            return None
    
    def determine_dptype(type) -> DPType | None:
        """Determine the DPType.

        Sometimes, we get ill-formed DPTypes from the cloud,
        this fixes them and maps them to the correct DPType.
        """
        try:
            return DPType(type)
        except ValueError:
            return TUYA_DPTYPE_MAPPING.get(type)