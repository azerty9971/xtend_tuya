from __future__ import annotations

from ...const import (
    DPType,
)

def prepare_value_for_property_update(dp_item, value) -> str:
    config_item = dp_item.get("config_item", None)
    if config_item is not None:
        value_type = config_item.get("valueType", None)
        if value_type is not None:
            if value_type == DPType.BOOLEAN:
                if bool(value):
                    return 'true'
                else:
                    return 'false'
    return str(value)