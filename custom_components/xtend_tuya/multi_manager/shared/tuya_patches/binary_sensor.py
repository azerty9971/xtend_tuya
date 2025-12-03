from __future__ import annotations

import homeassistant.components.tuya.binary_sensor as binary_sensor

from ....ha_tuya_integration.tuya_integration_imports import (
    TuyaCustomerDevice,
    TuyaBinarySensorEntityDescription,
    TuyaDPCodeWrapper,
    TuyaBinarySensorCustomDPCodeWrapper,
    TuyaDPCodeBitmapBitWrapper,
    TuyaDPCodeBooleanWrapper,
)

from ..decorator import (
    XTDecorator,
)

class XTTuyaBinarySensorPatcher:

    @staticmethod
    def patch_tuya():
        decorator, binary_sensor._get_dpcode_wrapper = XTDecorator.get_decorator(
            base_object=binary_sensor,
            callback=XTTuyaBinarySensorPatcher.on_get_dpcode_wrapper,
            method_name="_get_dpcode_wrapper",
            skip_call=True
        )

    @staticmethod
    def on_get_dpcode_wrapper(before_call: bool, base_object, *args, **kwargs)-> TuyaDPCodeWrapper | None:
        if before_call is True:
            return _get_dpcode_wrapper(*args, **kwargs)

def _get_dpcode_wrapper(
    device: TuyaCustomerDevice,
    description: TuyaBinarySensorEntityDescription,
) -> TuyaDPCodeWrapper | None:
    """Get DPCode wrapper for an entity description."""
    dpcode = description.dpcode or description.key
    if description.bitmap_key is not None:
        return TuyaDPCodeBitmapBitWrapper.find_dpcode(
            device, dpcode, bitmap_key=description.bitmap_key
        )

    if bool_type := TuyaDPCodeBooleanWrapper.find_dpcode(device, dpcode):
        return bool_type

    # Legacy / compatibility
    if dpcode not in device.status:
        return None
    return TuyaBinarySensorCustomDPCodeWrapper(
        dpcode, # type: ignore
        description.on_value
        if isinstance(description.on_value, set)
        else {description.on_value},
    )