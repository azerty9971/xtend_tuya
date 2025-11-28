from __future__ import annotations

from ....ha_tuya_integration.tuya_integration_imports import (
    TuyaCustomerDevice,
    TuyaDPCode,
    TuyaDPType,
    TuyaTypeInformation,
    TUYA_TYPE_INFORMATION_MAPPINGS,
    tuya_util_parse_dptype,
)

from ..decorator import (
    XTDecorator,
)
import homeassistant.components.tuya.models as tuya_model

class XTTuyaModelPatcher:

    @staticmethod
    def patch_tuya():
        decorator, tuya_model.find_dpcode = XTDecorator.get_decorator(
            base_object=tuya_model,
            callback=XTTuyaModelPatcher.on_find_dpcode,
            method_name="find_dpcode",
            skip_call=True
        )

    @staticmethod
    def on_find_dpcode(before_call: bool, base_object, *args, **kwargs)-> TuyaTypeInformation | None:
        if before_call is True:
            return find_dpcode(*args, **kwargs)



def find_dpcode(
    device: TuyaCustomerDevice,
    dpcodes: str | TuyaDPCode | tuple[TuyaDPCode, ...] | tuple[str, ...] | None,
    *,
    prefer_function: bool = False,
    dptype: TuyaDPType,
) -> TuyaTypeInformation | None:
    """Find type information for a matching DP code available for this device."""
    if not (type_information_cls := TUYA_TYPE_INFORMATION_MAPPINGS.get(dptype)):
        raise NotImplementedError(f"find_dpcode not supported for {dptype}")

    if dpcodes is None:
        return None

    if isinstance(dpcodes, str):
        dpcodes = (dpcodes,)
    elif not isinstance(dpcodes, tuple):
        dpcodes = (dpcodes,)

    lookup_tuple = (
        (device.function, device.status_range)
        if prefer_function
        else (device.status_range, device.function)
    )

    for dpcode in dpcodes:
        for device_specs in lookup_tuple:
            if (
                (current_definition := device_specs.get(dpcode))
                and tuya_util_parse_dptype(current_definition.type) is dptype
                and (
                    type_information := type_information_cls.from_json(
                        dpcode=dpcode, type_data=current_definition.values # type: ignore
                    )
                )
            ):
                return type_information

    return None