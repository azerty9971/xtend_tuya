"""Charging switch of the dé EV charger."""

from __future__ import annotations
from dataclasses import dataclass
from tuya_device_handlers.definition.switch import (
    SwitchDefinition,
)
from ...switch import (
    XTSwitchEntity,
    XTSwitchEntityDescription,
)
from ...multi_manager.multi_manager import (
    XTDevice,
    MultiManager,
)
from ...ha_tuya_integration.tuya_integration_imports import (
    TuyaCustomerDevice,
    TuyaDPCodeBooleanWrapper,
)
from .const import (
    CHARGING_WORK_STATES,
    DE_EV_CHARGER_CATEGORY,
    DeEVChargerDPCode,
)


class DeEVChargingSwitchWrapper(TuyaDPCodeBooleanWrapper):
    """Start/stop charging, the state is read from the work state.

    x_do_charge is write only: true starts, false stops charging. The switch
    is on while the charger reports that it is charging.
    """

    def read_device_status(self, device: TuyaCustomerDevice) -> bool | None:
        """Read the device value for the dpcode."""
        if (work_state := device.status.get(DeEVChargerDPCode.X_WORK_STATE)) is None:
            return None
        try:
            return int(work_state) in CHARGING_WORK_STATES
        except (TypeError, ValueError):
            return None

    def skip_update(
        self,
        device: TuyaCustomerDevice,
        updated_status_properties: list[str],
        dp_timestamps: dict[str, int] | None = None,
    ) -> bool:
        """Update when the start/stop or the work state DPCode changes."""
        return (
            self.dpcode not in updated_status_properties
            and DeEVChargerDPCode.X_WORK_STATE not in updated_status_properties
        )


@dataclass(frozen=True)
class DeEVChargingSwitchEntityDescription(XTSwitchEntityDescription):
    """Charging switch using DeEVChargingSwitchWrapper."""

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSwitchEntityDescription,
        definition: SwitchDefinition,
    ) -> XTSwitchEntity:
        if wrapper := DeEVChargingSwitchWrapper.find_dpcode(
            device, description.key, prefer_function=True
        ):
            definition = SwitchDefinition(switch_wrapper=wrapper)
        return XTSwitchEntity(
            device=device,
            device_manager=device_manager,
            description=description,
            definition=definition,
        )


DE_EV_CHARGER_SWITCHES: dict[str, tuple[XTSwitchEntityDescription, ...]] = {
    DE_EV_CHARGER_CATEGORY: (
        DeEVChargingSwitchEntityDescription(
            key=DeEVChargerDPCode.X_DO_CHARGE,
            translation_key="qt_ev_charging",
        ),
    ),
}
