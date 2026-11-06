"""Numbers of the dé EV charger."""

from __future__ import annotations
from homeassistant.components.number import (
    NumberDeviceClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
)
from ...number import (
    XTNumberEntityDescription,
)
from .const import (
    DE_EV_CHARGER_CATEGORY,
    DeEVChargerDPCode,
)

DE_EV_CHARGER_NUMBERS: dict[str, tuple[XTNumberEntityDescription, ...]] = {
    DE_EV_CHARGER_CATEGORY: (
        XTNumberEntityDescription(
            key=DeEVChargerDPCode.X_CHARGE_CURRENT,
            translation_key="qt_ev_charge_current",
            device_class=NumberDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        ),
        # Maximum current of the installation, changing it is rarely needed
        XTNumberEntityDescription(
            key=DeEVChargerDPCode.X_MAX_CURRENT_CFG,
            translation_key="qt_ev_max_current",
            device_class=NumberDeviceClass.CURRENT,
            native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            entity_category=EntityCategory.CONFIG,
            entity_registry_enabled_default=False,
        ),
    ),
}
