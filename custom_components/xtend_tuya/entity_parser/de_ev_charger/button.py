"""Buttons of the dé EV charger."""

from __future__ import annotations
from homeassistant.components.button import (
    ButtonDeviceClass,
)
from homeassistant.const import (
    EntityCategory,
)
from ...button import (
    XTButtonEntityDescription,
)
from .const import (
    DE_EV_CHARGER_CATEGORY,
    DeEVChargerDPCode,
)

DE_EV_CHARGER_BUTTONS: dict[str, tuple[XTButtonEntityDescription, ...]] = {
    DE_EV_CHARGER_CATEGORY: (
        XTButtonEntityDescription(
            key=DeEVChargerDPCode.X_DO_REBOOT,
            device_class=ButtonDeviceClass.RESTART,
            entity_category=EntityCategory.CONFIG,
        ),
    ),
}
