"""Support for Tuya sensors."""

from __future__ import annotations
import asyncio
import base64
from typing import cast, Callable, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime, UTC
from homeassistant.helpers import entity_registry as er
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
    SensorExtraStoredData,
    RestoreSensor,
)
from homeassistant.components.sensor.const import (
    DEVICE_CLASS_UNITS as SENSOR_DEVICE_CLASS_UNITS,
)
from homeassistant.components.recorder.models.statistics import (
    StatisticMeanType,
    StatisticMetaData,
    StatisticData,
)
from homeassistant.components.recorder.db_schema import (
    Statistics,
    StatisticsShortTerm,
)
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfTime,
    Platform,
    PERCENTAGE,
    EntityCategory,
)
from homeassistant.core import (
    HomeAssistant,
    callback,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_time_change,
)
from homeassistant.helpers.typing import (
    StateType,
)
from homeassistant.helpers.recorder import (
    get_instance as get_recorder_instance,
)
from .util import (
    get_default_value,
    restrict_descriptor_category,
    b64todatetime,
)
from .const import (
    TUYA_DISCOVERY_NEW,
    XTDPCode,
    VirtualStates,
    XTDeviceEntityFunctions,
    CROSS_CATEGORY_DEVICE_DESCRIPTOR,
    XTMultiManagerPostSetupCallbackPriority,
    LOGGER,
    XTMultiManagerProperties,
    XTDeviceWatcherCategory,
)
from .entity import (
    XTEntity,
    XTEntityDescriptorManager,
)
from .ha_tuya_integration.tuya_integration_imports import (
    TuyaSensorEntity,
    TuyaSensorEntityDescription,
    TuyaDPCode,
    TuyaIntegerTypeInformation,
    TuyaDPCodeWrapper,
    TuyaDPCodeBooleanWrapper,
    TuyaDPCodeIntegerWrapper,
    TuyaDPCodeEnumWrapper,
    TuyaDPCodeStringWrapper,
    TuyaCustomerDevice,
)
from tuya_device_handlers.definition.sensor import (
    SensorDefinition,
    get_default_definition,
)
from .multi_manager.shared.threading import (
    XTEventLoopProtector,
)
from .models import (
    XTDPCodeIntegerNoMinMaxCheckWrapper,
)
from tuya_device_handlers.device_wrapper.sensor import (
    ElectricityCurrentJsonWrapper,
    ElectricityCurrentRawWrapper,
    ElectricityPowerJsonWrapper,
    ElectricityPowerRawWrapper,
    ElectricityVoltageJsonWrapper,
    ElectricityVoltageRawWrapper,
)
from tuya_device_handlers.raw_data_model import (
    ElectricityData,
)

if TYPE_CHECKING:
    from .multi_manager.multi_manager import (
        XTConfigEntry,
        MultiManager,
        XTDevice,
    )

COMPOUND_KEY: list[str | tuple[str, ...]] = ["key", "dpcode"]


class XTElectricityCurrentStringWrapper(TuyaDPCodeStringWrapper[float]):
    """Custom DPCode Wrapper for extracting electricity current from base64."""

    native_unit = "mA"
    suggested_unit = "A"

    def read_device_status(self, device: TuyaCustomerDevice) -> float | None:
        """Read the device value for the dpcode."""
        if (raw_value := self._read_dpcode_value(device)) is None or (
            value := ElectricityData.from_bytes(base64.b64decode(raw_value))
        ) is None:
            return None
        return value.current


class XTElectricityPowerStringWrapper(TuyaDPCodeStringWrapper[float]):
    """Custom DPCode Wrapper for extracting electricity power from base64."""

    native_unit = "W"
    suggested_unit = "kW"

    def read_device_status(self, device: TuyaCustomerDevice) -> float | None:
        """Read the device value for the dpcode."""
        if (raw_value := self._read_dpcode_value(device)) is None or (
            value := ElectricityData.from_bytes(base64.b64decode(raw_value))
        ) is None:
            return None
        return value.power


class XTElectricityVoltageStringWrapper(TuyaDPCodeStringWrapper[float]):
    """Custom DPCode Wrapper for extracting electricity voltage from base64."""

    native_unit = "V"

    def read_device_status(self, device: TuyaCustomerDevice) -> float | None:
        """Read the device value for the dpcode."""
        if (raw_value := self._read_dpcode_value(device)) is None or (
            value := ElectricityData.from_bytes(base64.b64decode(raw_value))
        ) is None:
            return None
        return value.voltage


CURRENT_WRAPPER = (
    ElectricityCurrentRawWrapper,
    ElectricityCurrentJsonWrapper,
    XTElectricityCurrentStringWrapper,
)
POWER_WRAPPER = (
    ElectricityPowerRawWrapper,
    ElectricityPowerJsonWrapper,
    XTElectricityPowerStringWrapper,
)
VOLTAGE_WRAPPER = (
    ElectricityVoltageRawWrapper,
    ElectricityVoltageJsonWrapper,
    XTElectricityVoltageStringWrapper,
)


def xt_get_generic_dpcode_wrapper(
    device: XTDevice,
    description: TuyaSensorEntityDescription,
) -> TuyaDPCodeWrapper | None:
    """Get DPCode wrapper for an entity description."""
    dpcode = description.dpcode or description.key
    wrapper: TuyaDPCodeWrapper | None

    if description.wrapper_class:
        for cls in description.wrapper_class:
            if wrapper := cls.find_dpcode(device, dpcode):
                return wrapper
        return None

    for cls in (
        TuyaDPCodeIntegerWrapper,
        TuyaDPCodeEnumWrapper,
        TuyaDPCodeStringWrapper,
    ):
        if wrapper := cls.find_dpcode(device, dpcode):
            return wrapper

    return None


def xt_get_default_definition(
    device: XTDevice,
    description: TuyaSensorEntityDescription,
    device_manager: MultiManager,
) -> SensorDefinition | None:
    dpcode = description.dpcode or description.key
    if isinstance(description, XTSensorEntityDescription):
        if description.recalculate_scale_for_percentage:
            device_manager.execute_device_entity_function(
                XTDeviceEntityFunctions.RECALCULATE_PERCENT_SCALE,
                device,
                function_code=dpcode,
                scale_threshold=description.recalculate_scale_for_percentage_threshold,
            )
    return get_default_definition(
        device=device, dpcode=dpcode, wrapper_class=description.wrapper_class
    )


@dataclass(frozen=True)
class XTSensorEntityDescription(TuyaSensorEntityDescription, frozen=True):
    """Describes XT sensor entity."""

    dpcode: XTDPCode | TuyaDPCode | str | None = None  # type: ignore

    virtual_state: VirtualStates | None = None
    vs_copy_to_state: list[XTDPCode] = field(default_factory=list)
    vs_copy_delta_to_state: list[XTDPCode] = field(default_factory=list)

    reset_daily: bool = False
    reset_monthly: bool = False
    reset_yearly: bool = False
    restoredata: bool = False
    refresh_device_after_load: bool = False
    recalculate_scale_for_percentage: bool = False

    # Maximum percentage that the sensor can display (default = 100%)
    recalculate_scale_for_percentage_threshold: int = 999

    # Custom native_value function
    native_value: Callable | None = None

    # duplicate the entity if handled by another integration
    ignore_other_dp_code_handler: bool = False

    def get_entity_instance(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSensorEntityDescription,
        definition: SensorDefinition,
        supported_descriptors: dict[str, tuple[XTSensorEntityDescription, ...]],
    ) -> XTSensorEntity:
        return XTSensorEntity(
            device=device,
            device_manager=device_manager,
            description=XTSensorEntityDescription(**description.__dict__),
            definition=definition,
            supported_descriptors=supported_descriptors,
        )


# Commonly used battery sensors, that are re-used in the sensors down below.
BATTERY_SENSORS: tuple[XTSensorEntityDescription, ...] = (
    XTSensorEntityDescription(
        key=XTDPCode.BATTERY_PERCENTAGE,
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        recalculate_scale_for_percentage=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.BATTERY,  # Used by non-standard contact sensor implementations
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        recalculate_scale_for_percentage=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.BATTERY_STATE,
        translation_key="battery_state",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.BATTERY_VALUE,
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        recalculate_scale_for_percentage=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.VA_BATTERY,
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        recalculate_scale_for_percentage=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.RESIDUAL_ELECTRICITY,
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        recalculate_scale_for_percentage=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.BATTERY_POWER,
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        recalculate_scale_for_percentage=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.WIRELESS_ELECTRICITY,
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        recalculate_scale_for_percentage=True,
    ),
)

# Commonly used energy sensors, that are re-used in the sensors down below.
CONSUMPTION_SENSORS: tuple[XTSensorEntityDescription, ...] = (
    XTSensorEntityDescription(
        key=XTDPCode.ADD_ELE,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME
        | VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        vs_copy_to_state=[
            XTDPCode.ADD_ELE_TODAY,
            XTDPCode.ADD_ELE_THIS_MONTH,
            XTDPCode.ADD_ELE_THIS_YEAR,
            XTDPCode.XT_ADD_ELE,
        ],
        vs_copy_delta_to_state=[],
        translation_key="add_ele",
        translation_placeholders={"index": "1"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        ignore_other_dp_code_handler=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ADD_ELE_TODAY,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="add_ele_today",
        translation_placeholders={"index": "1"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        reset_daily=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ADD_ELE_THIS_MONTH,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="add_ele_this_month",
        translation_placeholders={"index": "1"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        reset_monthly=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ADD_ELE_THIS_YEAR,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="add_ele_this_year",
        translation_placeholders={"index": "1"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        reset_yearly=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        # The ADD_ELE2 dpcode takes the opposite direction than ADD_ELE, if ADD_ELE is supposed
        # to contain an incremental value, ADD_ELE2 assumes a total value
        # same logic but reversed, if ADD_ELE should report a total value then we assume that
        # ADD_ELE2 is an incremental
        key=XTDPCode.XT_ADD_ELE,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME,
        vs_copy_to_state=[
            XTDPCode.XT_ADD_ELE_TODAY,
            XTDPCode.XT_ADD_ELE_THIS_MONTH,
            XTDPCode.XT_ADD_ELE_THIS_YEAR,
        ],
        translation_key="xt_add_ele",
        translation_placeholders={"index": "1"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
        ignore_other_dp_code_handler=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.XT_ADD_ELE_TODAY,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="xt_add_ele_today",
        translation_placeholders={"index": "1"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
        reset_daily=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.XT_ADD_ELE_THIS_MONTH,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="xt_add_ele_this_month",
        translation_placeholders={"index": "1"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
        reset_monthly=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.XT_ADD_ELE_THIS_YEAR,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="xt_add_ele_this_year",
        translation_placeholders={"index": "1"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
        reset_yearly=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ADD_ELE2,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME
        | VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        vs_copy_to_state=[
            XTDPCode.ADD_ELE2_TODAY,
            XTDPCode.ADD_ELE2_THIS_MONTH,
            XTDPCode.ADD_ELE2_THIS_YEAR,
            XTDPCode.XT_ADD_ELE2,
        ],
        vs_copy_delta_to_state=[],
        translation_key="add_ele",
        translation_placeholders={"index": "2"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        ignore_other_dp_code_handler=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ADD_ELE2_TODAY,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="add_ele_today",
        translation_placeholders={"index": "2"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        reset_daily=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ADD_ELE2_THIS_MONTH,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="add_ele_this_month",
        translation_placeholders={"index": "2"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        reset_monthly=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ADD_ELE2_THIS_YEAR,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="add_ele_this_year",
        translation_placeholders={"index": "2"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        reset_yearly=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        # The ADD_ELE2 dpcode takes the opposite direction than ADD_ELE, if ADD_ELE is supposed
        # to contain an incremental value, ADD_ELE2 assumes a total value
        # same logic but reversed, if ADD_ELE should report a total value then we assume that
        # ADD_ELE2 is an incremental
        key=XTDPCode.XT_ADD_ELE2,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME,
        vs_copy_to_state=[
            XTDPCode.XT_ADD_ELE2_TODAY,
            XTDPCode.XT_ADD_ELE2_THIS_MONTH,
            XTDPCode.XT_ADD_ELE2_THIS_YEAR,
        ],
        translation_key="xt_add_ele",
        translation_placeholders={"index": "2"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
        ignore_other_dp_code_handler=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.XT_ADD_ELE2_TODAY,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="xt_add_ele_today",
        translation_placeholders={"index": "2"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
        reset_daily=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.XT_ADD_ELE2_THIS_MONTH,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="xt_add_ele_this_month",
        translation_placeholders={"index": "2"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
        reset_monthly=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.XT_ADD_ELE2_THIS_YEAR,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="xt_add_ele_this_year",
        translation_placeholders={"index": "2"},
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
        reset_yearly=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.BALANCE_ENERGY,
        translation_key="balance_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        restoredata=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CHARGE_ENERGY,
        translation_key="charge_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        restoredata=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CHARGE_ENERGY_ONCE,
        translation_key="charge_energy_once",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        restoredata=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.DEVICEKWH,
        translation_key="device_consumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        restoredata=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ELECTRIC,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME
        | VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        vs_copy_to_state=[
            XTDPCode.ELECTRIC_TODAY,
            XTDPCode.ELECTRIC_THIS_MONTH,
            XTDPCode.ELECTRIC_THIS_YEAR,
        ],
        translation_key="electric",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        restoredata=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ELECTRIC_TODAY,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="electric_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        restoredata=True,
        reset_daily=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ELECTRIC_THIS_MONTH,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="electric_this_month",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        restoredata=True,
        reset_monthly=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ELECTRIC_THIS_YEAR,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="electric_this_year",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        reset_yearly=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ENERGYCONSUMED,
        translation_key="energyconsumed",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ENERGYCONSUMEDA,
        translation_key="energyconsumeda",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ENERGYCONSUMEDB,
        translation_key="energyconsumedb",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ENERGYCONSUMEDC,
        translation_key="energyconsumedc",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.FORWARD_ENERGY_TOTAL,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME,
        vs_copy_to_state=[
            XTDPCode.XT_FORWARD_ENERGY_TOTAL,
        ],
        vs_copy_delta_to_state=[
            XTDPCode.FORWARD_ENERGY_TOTAL_TODAY,
            XTDPCode.FORWARD_ENERGY_TOTAL_THIS_MONTH,
            XTDPCode.FORWARD_ENERGY_TOTAL_THIS_YEAR,
        ],
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        restoredata=True,
        ignore_other_dp_code_handler=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.FORWARD_ENERGY_TOTAL_TODAY,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="total_energy_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        reset_daily=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.FORWARD_ENERGY_TOTAL_THIS_MONTH,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="total_energy_this_month",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        reset_monthly=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.FORWARD_ENERGY_TOTAL_THIS_YEAR,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="total_energy_this_year",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        reset_yearly=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        # The ADD_ELE2 dpcode takes the opposite direction than ADD_ELE, if ADD_ELE is supposed
        # to contain an incremental value, ADD_ELE2 assumes a total value
        # same logic but reversed, if ADD_ELE should report a total value then we assume that
        # ADD_ELE2 is an incremental
        key=XTDPCode.XT_FORWARD_ENERGY_TOTAL,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME,
        vs_copy_to_state=[
            XTDPCode.XT_FORWARD_ENERGY_TOTAL_TODAY,
            XTDPCode.XT_FORWARD_ENERGY_TOTAL_THIS_MONTH,
            XTDPCode.XT_FORWARD_ENERGY_TOTAL_THIS_YEAR,
        ],
        translation_key="xt_total_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
        ignore_other_dp_code_handler=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.XT_FORWARD_ENERGY_TOTAL_TODAY,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="xt_total_energy_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
        reset_daily=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.XT_FORWARD_ENERGY_TOTAL_THIS_MONTH,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="xt_total_energy_this_month",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
        reset_monthly=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.XT_FORWARD_ENERGY_TOTAL_THIS_YEAR,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="xt_total_energy_this_year",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
        reset_yearly=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.POWER_CONSUMPTION,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME
        | VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        vs_copy_to_state=[
            XTDPCode.ADD_ELE_TODAY,
            XTDPCode.ADD_ELE_THIS_MONTH,
            XTDPCode.ADD_ELE_THIS_YEAR,
            XTDPCode.XT_ADD_ELE,
        ],
        vs_copy_delta_to_state=[],
        translation_key="add_ele",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        ignore_other_dp_code_handler=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.REVERSE_ENERGY_A,
        translation_key="gross_generation_a",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.REVERSE_ENERGY_B,
        translation_key="gross_generation_b",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.REVERSE_ENERGY_C,
        translation_key="gross_generation_c",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.REVERSE_ENERGY_T,
        translation_key="gross_generation",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.REVERSE_ENERGY_TOTAL,
        translation_key="gross_generation",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        restoredata=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TOTALENERGYCONSUMED,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME,
        vs_copy_to_state=[
            XTDPCode.XT_ADD_ELE,
        ],
        vs_copy_delta_to_state=[
            XTDPCode.ADD_ELE_TODAY,
            XTDPCode.ADD_ELE_THIS_MONTH,
            XTDPCode.ADD_ELE_THIS_YEAR,
        ],
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        restoredata=True,
        ignore_other_dp_code_handler=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TOTAL_FORWARD_ENERGY,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME,
        vs_copy_to_state=[
            XTDPCode.XT_TOTAL_FORWARD_ENERGY,
        ],
        vs_copy_delta_to_state=[
            XTDPCode.TOTAL_FORWARD_ENERGY_TODAY,
            XTDPCode.TOTAL_FORWARD_ENERGY_THIS_MONTH,
            XTDPCode.TOTAL_FORWARD_ENERGY_THIS_YEAR,
        ],
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        restoredata=True,
        ignore_other_dp_code_handler=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TOTAL_FORWARD_ENERGY_TODAY,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="total_energy_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        reset_daily=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TOTAL_FORWARD_ENERGY_THIS_MONTH,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="total_energy_this_month",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        reset_monthly=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TOTAL_FORWARD_ENERGY_THIS_YEAR,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="total_energy_this_year",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=True,
        restoredata=True,
        reset_yearly=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        # The ADD_ELE2 dpcode takes the opposite direction than ADD_ELE, if ADD_ELE is supposed
        # to contain an incremental value, ADD_ELE2 assumes a total value
        # same logic but reversed, if ADD_ELE should report a total value then we assume that
        # ADD_ELE2 is an incremental
        key=XTDPCode.XT_TOTAL_FORWARD_ENERGY,
        virtual_state=VirtualStates.STATE_COPY_TO_MULTIPLE_STATE_NAME,
        vs_copy_to_state=[
            XTDPCode.XT_TOTAL_FORWARD_ENERGY_TODAY,
            XTDPCode.XT_TOTAL_FORWARD_ENERGY_THIS_MONTH,
            XTDPCode.XT_TOTAL_FORWARD_ENERGY_THIS_YEAR,
        ],
        translation_key="xt_total_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
        ignore_other_dp_code_handler=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.XT_TOTAL_FORWARD_ENERGY_TODAY,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="xt_total_energy_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
        reset_daily=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.XT_TOTAL_FORWARD_ENERGY_THIS_MONTH,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="xt_total_energy_this_month",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
        reset_monthly=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
    XTSensorEntityDescription(
        key=XTDPCode.XT_TOTAL_FORWARD_ENERGY_THIS_YEAR,
        virtual_state=VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD,
        translation_key="xt_total_energy_this_year",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        entity_registry_enabled_default=False,
        restoredata=True,
        reset_yearly=True,
        wrapper_class=(XTDPCodeIntegerNoMinMaxCheckWrapper,),
    ),
)

TEMPERATURE_SENSORS: tuple[XTSensorEntityDescription, ...] = (
    XTSensorEntityDescription(
        key=XTDPCode.TEMPERATURE,
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TEMPERATURE2,
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TEMP2,
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TEMP_CURRENT,
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TEMP_INDOOR,
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TEMP_VALUE,
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TEMP_TOP,
        translation_key="temp_top",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TEMP_BOTTOM,
        translation_key="temp_bottom",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.DEVICETEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        translation_key="device_temperature",
    ),
    XTSensorEntityDescription(
        key=XTDPCode.DEVICETEMP2,
        device_class=SensorDeviceClass.TEMPERATURE,
        translation_key="device_temperature2",
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TEMPSHOW,
        device_class=SensorDeviceClass.TEMPERATURE,
        translation_key="temp_show",
    ),
    XTSensorEntityDescription(
        key=XTDPCode.TEMP_ALARM,
        translation_key="temp_alarm",
    ),
)

HUMIDITY_SENSORS: tuple[XTSensorEntityDescription, ...] = (
    XTSensorEntityDescription(
        key=XTDPCode.HUMIDITY,
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.HUMIDITY1,
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.HUMIDITY_VALUE,
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.HUMIDITY_INDOOR,
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.HUM_ALARM,
        translation_key="hum_alarm",
    ),
)

ELECTRICITY_SENSORS: tuple[XTSensorEntityDescription, ...] = (
    XTSensorEntityDescription(
        key=XTDPCode.ACHZ,
        translation_key="achz",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.FREQUENCY,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ACTIVEPOWER,
        translation_key="activepower",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ACTIVEPOWERA,
        translation_key="activepowera",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ACTIVEPOWERB,
        translation_key="activepowerb",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ACTIVEPOWERC,
        translation_key="activepowerc",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ACV,
        translation_key="acv",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ACI,
        translation_key="aci",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.A_CURRENT,
        translation_key="a_current",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.A_VOLTAGE,
        translation_key="a_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.B_CURRENT,
        translation_key="b_current",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.B_VOLTAGE,
        translation_key="b_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CUR_CURRENT2,
        translation_key="current2",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CUR_POWER,
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CUR_POWER2,
        translation_key="power2",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CUR_VOLTAGE2,
        translation_key="voltage2",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CURRENT,
        translation_key="current",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CURRENT_A,
        translation_key="current_a",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CURRENT_B,
        translation_key="current_b",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CURRENTA,
        translation_key="currenta",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CURRENTB,
        translation_key="currentb",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CURRENTC,
        translation_key="currentc",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CURRENT_YD,
        translation_key="current",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.C_CURRENT,
        translation_key="c_current",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.C_VOLTAGE,
        translation_key="c_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.DEVICEKW,
        translation_key="device_power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.DEVICEMAXSETA,
        translation_key="device_max_set_a",
    ),
    XTSensorEntityDescription(
        key=XTDPCode.DIRECTION_A,
        translation_key="direction_a",
    ),
    XTSensorEntityDescription(
        key=XTDPCode.DIRECTION_B,
        translation_key="direction_b",
    ),
    XTSensorEntityDescription(
        key=XTDPCode.ELECTRIC_TOTAL,
        translation_key="electric_total",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.PHASEFLAG,
        translation_key="phaseflag",
    ),
    XTSensorEntityDescription(
        key=f"{XTDPCode.PHASE_A}electriccurrent",
        dpcode=XTDPCode.PHASE_A,
        translation_key="phase_a_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        wrapper_class=CURRENT_WRAPPER,
    ),
    XTSensorEntityDescription(
        key=f"{XTDPCode.PHASE_A}power",
        dpcode=XTDPCode.PHASE_A,
        translation_key="phase_a_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        wrapper_class=POWER_WRAPPER,
    ),
    XTSensorEntityDescription(
        key=f"{XTDPCode.PHASE_A}voltage",
        dpcode=XTDPCode.PHASE_A,
        translation_key="phase_a_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        wrapper_class=VOLTAGE_WRAPPER,
    ),
    XTSensorEntityDescription(
        key=f"{XTDPCode.PHASE_B}electriccurrent",
        dpcode=XTDPCode.PHASE_B,
        translation_key="phase_b_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        wrapper_class=CURRENT_WRAPPER,
    ),
    XTSensorEntityDescription(
        key=f"{XTDPCode.PHASE_B}power",
        dpcode=XTDPCode.PHASE_B,
        translation_key="phase_b_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        wrapper_class=POWER_WRAPPER,
    ),
    XTSensorEntityDescription(
        key=f"{XTDPCode.PHASE_B}voltage",
        dpcode=XTDPCode.PHASE_B,
        translation_key="phase_b_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        wrapper_class=VOLTAGE_WRAPPER,
    ),
    XTSensorEntityDescription(
        key=f"{XTDPCode.PHASE_C}electriccurrent",
        dpcode=XTDPCode.PHASE_C,
        translation_key="phase_c_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        wrapper_class=CURRENT_WRAPPER,
    ),
    XTSensorEntityDescription(
        key=f"{XTDPCode.PHASE_C}power",
        dpcode=XTDPCode.PHASE_C,
        translation_key="phase_c_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        wrapper_class=POWER_WRAPPER,
    ),
    XTSensorEntityDescription(
        key=f"{XTDPCode.PHASE_C}voltage",
        dpcode=XTDPCode.PHASE_C,
        translation_key="phase_c_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        wrapper_class=VOLTAGE_WRAPPER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.POWERFACTORA,
        translation_key="powerfactora",
    ),
    XTSensorEntityDescription(
        key=XTDPCode.POWERFACTORB,
        translation_key="powerfactorb",
    ),
    XTSensorEntityDescription(
        key=XTDPCode.POWERFACTORC,
        translation_key="powerfactorc",
    ),
    XTSensorEntityDescription(
        key=XTDPCode.POWER_TOTAL,
        translation_key="power_total",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.PV1_VOLT,
        translation_key="pv1_volt",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.PV2_VOLT,
        translation_key="pv2_volt",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.PVV,
        translation_key="pvv",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.PV1_CURR,
        translation_key="pv1_curr",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.PV2_CURR,
        translation_key="pv2_curr",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.PVI,
        translation_key="pvi",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.POWER_A,
        translation_key="power_a",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.POWER_B,
        translation_key="power_b",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.REACTIVEPOWER,
        translation_key="reactivepower",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.REACTIVE_POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.REACTIVEPOWERA,
        translation_key="reactivepowera",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.REACTIVE_POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.REACTIVEPOWERB,
        translation_key="reactivepowerb",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.REACTIVE_POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.REACTIVEPOWERC,
        translation_key="reactivepowerc",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.REACTIVE_POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.SIGLE_PHASE_POWER,
        translation_key="sigle_phase_power",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.VOL_YD,
        translation_key="voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.VOLTAGE_A,
        translation_key="voltage_a",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.VOLTAGEA,
        translation_key="a_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.VOLTAGEB,
        translation_key="b_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.VOLTAGEC,
        translation_key="c_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.VOLTAGE_CURRENT,
        translation_key="voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
)

TIMER_SENSORS: tuple[XTSensorEntityDescription, ...] = (
    XTSensorEntityDescription(
        key=XTDPCode.CTIME,
        translation_key="ctime",
        entity_registry_enabled_default=True,
    ),
    XTSensorEntityDescription(
        key=XTDPCode.CTIME2,
        translation_key="ctime2",
        entity_registry_enabled_default=True,
        entity_registry_visible_default=False,
    ),
)

LOCK_SENSORS: tuple[XTSensorEntityDescription, ...] = (
    XTSensorEntityDescription(
        key=XTDPCode.CLOSED_OPENED,
        translation_key="jtmspro_closed_opened",
        entity_registry_enabled_default=True,
    ),
)

# All descriptions can be found here. Mostly the Integer data types in the
# default status set of each category (that don't have a set instruction)
# end up being a sensor.
# https://developer.tuya.com/en/docs/iot/standarddescription?id=K9i5ql6waswzq
SENSORS: dict[str, tuple[XTSensorEntityDescription, ...]] = {
    CROSS_CATEGORY_DEVICE_DESCRIPTOR: (
        *CONSUMPTION_SENSORS,
        *BATTERY_SENSORS,
    ),
    "dbl": (
        XTSensorEntityDescription(
            key=XTDPCode.COUNTDOWN_LEFT,
            translation_key="countdown_left",
            entity_registry_enabled_default=False,
        ),
    ),
    "hps": (
        XTSensorEntityDescription(
            key=XTDPCode.PRESENCE_STATE,
            translation_key="hps_presence_state",
        ),
        XTSensorEntityDescription(
            key=XTDPCode.TARGET_DISTANCE,
            translation_key="target_distance",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.LDR,
            translation_key="ldr",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.ILLUMINANCE_VALUE,
            translation_key="illuminance_value",
            device_class=SensorDeviceClass.ILLUMINANCE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        # ZG-205Z specific DPs
        XTSensorEntityDescription(
            key=XTDPCode.MOV_STATUS,
            translation_key="mov_status",
        ),
        XTSensorEntityDescription(
            key=XTDPCode.DISTANCE,
            translation_key="distance",
            device_class=SensorDeviceClass.DISTANCE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.DETECTION_NEAR,
            translation_key="detection_near",
            device_class=SensorDeviceClass.DISTANCE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    # Formaldehyde Detector
    # Note: Not documented
    "jqbj": (
        XTSensorEntityDescription(
            key=XTDPCode.CH2O_STATE,
            translation_key="air_quality",
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.PM25_VALUE,
            translation_key="pm25",
            device_class=SensorDeviceClass.PM25,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.CO2_VALUE,
            translation_key="carbon_dioxide",
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.PM10,
            translation_key="pm10",
            device_class=SensorDeviceClass.PM10,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
    ),
    "jtmspro": (
        *LOCK_SENSORS,
        *ELECTRICITY_SENSORS,
    ),
    # Switch
    # https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
    "kg": (
        XTSensorEntityDescription(
            key=XTDPCode.ILLUMINANCE_VALUE,
            translation_key="illuminance_value",
            device_class=SensorDeviceClass.ILLUMINANCE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.METER_TYPE,
            translation_key="meter_type",
        ),
        XTSensorEntityDescription(
            key=XTDPCode.FREQUENCY,
            translation_key="frequency",
            device_class=SensorDeviceClass.FREQUENCY,
        ),
        *TEMPERATURE_SENSORS,
        *HUMIDITY_SENSORS,
        *ELECTRICITY_SENSORS,
    ),
    "MPPT": (
        XTSensorEntityDescription(
            key=XTDPCode.PRODUCT_SPECIFICATIONS,
            translation_key="product_specifications",
        ),
        XTSensorEntityDescription(
            key=XTDPCode.DEVICEID,
            translation_key="deviceid",
        ),
        XTSensorEntityDescription(
            key=XTDPCode.RELEASES,
            translation_key="releases",
        ),
        *TEMPERATURE_SENSORS,
        *ELECTRICITY_SENSORS,
    ),
    "ms": (*LOCK_SENSORS,),
    # Automatic cat litter box
    # Note: Undocumented
    "msp": (
        XTSensorEntityDescription(
            key=XTDPCode.AUTO_DEORDRIZER,
            translation_key="auto_deordrizer",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.CALIBRATION,
            translation_key="calibration",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        # capacity_calibration is configurable — defined as number in number.py
        XTSensorEntityDescription(
            key=XTDPCode.CAT_WEIGHT,
            translation_key="cat_weight",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.CLEAN_NOTICE,
            translation_key="clean_notice",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.CLEAN_TASTE,
            translation_key="clean_taste",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.CLEAN_TIME,
            translation_key="clean_time",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.DEODORIZATION_NUM,
            translation_key="ozone_concentration",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        # detection_sensitivity is configurable — defined as number in number.py
        XTSensorEntityDescription(
            key=XTDPCode.EXCRETION_TIME_DAY,
            translation_key="excretion_time_day",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTime.SECONDS,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.EXCRETION_TIMES_DAY,
            translation_key="excretion_times_day",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.HISTORY,
            translation_key="msp_history",
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.INDUCTION_CLEAN,
            translation_key="induction_clean",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        # induction_delay and induction_interval are configurable — defined as numbers in number.py
        XTSensorEntityDescription(
            key=XTDPCode.MONITORING,
            translation_key="monitoring",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.NET_NOTICE,
            translation_key="net_notice",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.NOT_DISTURB,
            translation_key="not_disturb",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.NOTIFICATION_STATUS,
            translation_key="notification_status",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.NUMBER,
            translation_key="number",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.ODOURLESS,
            translation_key="odourless",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.PEDAL_ANGLE,
            translation_key="pedal_angle",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.PIR_RADAR,
            translation_key="pir_radar",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        # sand_surface_calibration is configurable — defined as number in number.py
        XTSensorEntityDescription(
            key=XTDPCode.SMART_CLEAN,
            translation_key="smart_clean",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.STATUS,
            translation_key="cat_litter_box_status",
            # No state_class: values are string enums (standby, clean, empty, …), not numeric
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.STORE_FULL_NOTIFY,
            translation_key="store_full_notify",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.TOILET_NOTICE,
            translation_key="toilet_notice",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.UNIT,
            translation_key="unit",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.USAGE_TIMES,
            translation_key="usage_times",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.WORK_STAT,
            translation_key="work_stat",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        # Bag change usage counter — Ti+ / DOEL ti+TpCTbt-01
        XTSensorEntityDescription(
            key=XTDPCode.BAG_CHANGE_COUNTING,
            translation_key="bag_change_counting",
            state_class=SensorStateClass.TOTAL_INCREASING,
            entity_registry_enabled_default=True,
        ),
        # Cat weight in lb (read-only mirror of cat_weight in pounds) — Ti+ / DOEL ti+TpCTbt-01
        XTSensorEntityDescription(
            key=XTDPCode.PONUD,
            translation_key="ponud",
            device_class=SensorDeviceClass.WEIGHT,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        *TEMPERATURE_SENSORS,
    ),
    "ms_category": (*LOCK_SENSORS,),
    "mzj": (
        XTSensorEntityDescription(
            key=XTDPCode.REMAININGTIME,
            translation_key="remaining_time",
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.WORK_STATUS,
            translation_key="mzj_work_status",
            entity_registry_enabled_default=True,
        ),
        *TEMPERATURE_SENSORS,
    ),
    "pir": (
        XTSensorEntityDescription(
            key=XTDPCode.ILLUMINANCE_VALUE,
            translation_key="illuminance_value",
            device_class=SensorDeviceClass.ILLUMINANCE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
    ),
    "qccdz": (
        XTSensorEntityDescription(
            key=XTDPCode.CONNECTION_STATE,
            translation_key="qccdz_connection_state",
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.DEVICESTATE,
            translation_key="qccdz_devicestate",
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.SYSTEM_VERSION,
            translation_key="system_version",
            entity_registry_enabled_default=True,
            entity_registry_visible_default=False,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.WORK_STATE,
            translation_key="qccdz_work_state",
            entity_registry_enabled_default=True,
        ),
        *TEMPERATURE_SENSORS,
        *ELECTRICITY_SENSORS,
        *TIMER_SENSORS,
    ),
    "rs": (*TEMPERATURE_SENSORS,),
    # QT-08W Solar Intelligent Water Valve
    "sfkzq": (
        XTSensorEntityDescription(
            key=XTDPCode.WATER_ONCE,
            translation_key="water_once",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.WATER_TOTAL,
            translation_key="water_total",
            state_class=SensorStateClass.TOTAL_INCREASING,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.VBAT_STATE,
            translation_key="battery_level",
            device_class=SensorDeviceClass.BATTERY,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            native_value=lambda x: int(x) & 0x7F,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.CUR_CAP,
            translation_key="watering_volume",
            device_class=SensorDeviceClass.WATER,
            native_unit_of_measurement="L",
            suggested_display_precision=0,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.CYC_NUM,
            translation_key="watering_cycle",
            native_unit_of_measurement="",
            native_value=lambda x: int(x),
        ),
        XTSensorEntityDescription(
            key=XTDPCode.START_TIME,
            translation_key="start_time",
            device_class=SensorDeviceClass.TIMESTAMP,
            native_unit_of_measurement="",
            native_value=b64todatetime,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.CLOSE_TIME,
            translation_key="end_time",
            device_class=SensorDeviceClass.TIMESTAMP,
            native_unit_of_measurement="",
            native_value=b64todatetime,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.RUN_TASK_STA,
            translation_key="watering_task",
            native_unit_of_measurement="",
            native_value=lambda x: str(x),
        ),
    ),
    "slj": (
        XTSensorEntityDescription(
            key=XTDPCode.WATER_USE_DATA,
            translation_key="water_use_data",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.WATER_ONCE,
            translation_key="water_once",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.FLOW_VELOCITY,
            translation_key="flow_velocity",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        *ELECTRICITY_SENSORS,
    ),
    "smd": (
        XTSensorEntityDescription(
            key=XTDPCode.HEART_RATE,
            translation_key="heart_rate",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.RESPIRATORY_RATE,
            translation_key="respiratory_rate",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.SLEEP_STAGE,
            translation_key="sleep_stage",
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.TIME_GET_IN_BED,
            translation_key="time_get_in_bed",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.OFF_BED_TIME,
            translation_key="off_bed_time",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.CLCT_TIME,
            translation_key="clct_time",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
    ),
    "wk": (*TEMPERATURE_SENSORS,),
    "wnykq": (
        XTSensorEntityDescription(
            key=XTDPCode.IR_CONTROL,
            translation_key="wnykq_ir_control",
            entity_registry_enabled_default=True,
        ),
        *TEMPERATURE_SENSORS,
        *HUMIDITY_SENSORS,
    ),
    "wsdcg": (
        *TEMPERATURE_SENSORS,
        *HUMIDITY_SENSORS,
    ),
    "xfj": (
        XTSensorEntityDescription(
            key=XTDPCode.PM25,
            translation_key="pm25",
            device_class=SensorDeviceClass.PM25,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.ECO2,
            translation_key="concentration_carbon_dioxide",
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.FILTER_LIFE,
            translation_key="filter_life",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.TVOC,
            translation_key="tvoc",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.AIR_QUALITY,
            translation_key="air_quality",
        ),
        *TEMPERATURE_SENSORS,
        *HUMIDITY_SENSORS,
    ),
    "ywcgq": (
        XTSensorEntityDescription(
            key=XTDPCode.LIQUID_STATE,
            translation_key="liquid_state",
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.LIQUID_DEPTH,
            translation_key="liquid_depth",
            device_class=SensorDeviceClass.DISTANCE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.LIQUID_LEVEL_PERCENT,
            translation_key="liquid_level_percent",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=True,
            recalculate_scale_for_percentage=True,
            recalculate_scale_for_percentage_threshold=1000,
            suggested_display_precision=0,
        ),
        XTSensorEntityDescription(
            key=XTDPCode.BATTERY_PERCENTAGE,
            translation_key="voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            suggested_display_precision=1,
        ),
    ),
    # ZNRB devices don't send correct cloud data, for these devices use https://github.com/make-all/tuya-local instead
    # "znrb": (
    #    *TEMPERATURE_SENSORS,
    # ),
    "zwjcy": (
        *TEMPERATURE_SENSORS,
        *HUMIDITY_SENSORS,
    ),
}

# Socket (duplicate of `kg`)
# https://developer.tuya.com/en/docs/iot/s?id=K9gf7o5prgf7s
SENSORS["cz"] = SENSORS["kg"]
SENSORS["wkcz"] = SENSORS["kg"]
SENSORS["dlq"] = SENSORS["kg"]
SENSORS["tdq"] = SENSORS["kg"]
SENSORS["pc"] = SENSORS["kg"]
SENSORS["aqcz"] = SENSORS["kg"]
SENSORS["zndb"] = SENSORS["kg"]

# Lock duplicates
SENSORS["videolock"] = SENSORS["jtmspro"]
SENSORS["jtmsbh"] = SENSORS["jtmspro"]


async def async_setup_entry(
    hass: HomeAssistant, entry: XTConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Tuya sensor dynamically through Tuya discovery."""
    hass_data = entry.runtime_data
    this_platform = Platform.SENSOR
    if entry.runtime_data.multi_manager is None or hass_data.manager is None:
        return

    supported_descriptors, externally_managed_descriptors = cast(
        tuple[
            dict[str, tuple[XTSensorEntityDescription, ...]],
            dict[str, tuple[XTSensorEntityDescription, ...]],
        ],
        XTEntityDescriptorManager.get_platform_descriptors(
            SENSORS,
            entry.runtime_data.multi_manager,
            XTSensorEntityDescription,
            this_platform,
            COMPOUND_KEY,
        ),
    )

    @callback
    def async_add_generic_entities(device_map) -> None:
        if hass_data.manager is None:
            return
        entities: list[XTSensorEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                generic_dpcodes = XTEntity.get_generic_dpcodes_for_this_platform(
                    device, this_platform
                )
                hass_data.manager.device_watcher.report_message(
                    device_id,
                    f"Generic dpcodes for sensor: {generic_dpcodes=}",
                    XTDeviceWatcherCategory.PLATFORM_SENSOR,
                    device,
                )
                if not generic_dpcodes:
                    continue
                dev_class_from_uom = XTEntity.get_device_classes_from_uom(
                    SENSOR_DEVICE_CLASS_UNITS
                )
                for dpcode in generic_dpcodes:
                    dpcode_info = device.get_dpcode_information(dpcode=dpcode)
                    device_class = XTEntity.get_device_class_from_uom(
                        dpcode_info, dev_class_from_uom, device
                    )
                    state_class = (
                        XTSensorEntity.determine_state_class_from_dpcode_information(
                            dpcode_info, device_class
                        )
                    )
                    descriptor = XTSensorEntityDescription(
                        key=dpcode,
                        device_class=device_class,
                        state_class=state_class,
                        translation_key="xt_generic_sensor",
                        translation_placeholders={
                            "name": XTEntity.get_human_name(dpcode)
                        },
                        entity_registry_enabled_default=False,
                        entity_registry_visible_default=False,
                        wrapper_class=(
                            TuyaDPCodeStringWrapper,
                            TuyaDPCodeIntegerWrapper,
                            TuyaDPCodeEnumWrapper,
                            TuyaDPCodeBooleanWrapper,
                        ),
                    )
                    if definition := xt_get_default_definition(
                        device,
                        description=descriptor,
                        device_manager=hass_data.manager,
                    ):
                        entities.append(
                            XTSensorEntity.get_entity_instance(
                                descriptor,
                                device,
                                hass_data.manager,
                                definition,
                                supported_descriptors,
                            )
                        )
        async_add_entities(entities)

    @callback
    def async_discover_device(device_map, restrict_dpcode: str | None = None) -> None:
        """Discover and add a discovered Tuya sensor."""
        if hass_data.manager is None:
            return
        entities: list[XTSensorEntity] = []
        device_ids = [*device_map]
        for device_id in device_ids:
            if device := hass_data.manager.device_map.get(device_id):
                if category_descriptions := XTEntityDescriptorManager.get_category_descriptors(
                    supported_descriptors, device.category
                ):
                    externally_managed_dpcodes = (
                        XTEntityDescriptorManager.get_category_keys(
                            externally_managed_descriptors.get(device.category)
                        )
                    )
                    if restrict_dpcode is not None:
                        category_descriptions = cast(
                            tuple[XTSensorEntityDescription, ...],
                            restrict_descriptor_category(
                                category_descriptions, [restrict_dpcode]
                            ),
                        )
                    # for description in category_descriptions:
                    #     dpcode = description.dpcode or description.key
                    #     if (
                    #         hasattr(description, "virtual_state")
                    #         and description.virtual_state
                    #         and description.virtual_state & VirtualStates.STATE_SUMMED_IN_REPORTING_PAYLOAD
                    #         and (dpcode) in device.status_range
                    #     ):
                    #         device.status_range[dpcode].report_type = "sum"
                    entities.extend(
                        XTSensorEntity.get_entity_instance(
                            description,
                            device,
                            hass_data.manager,
                            definition,
                            supported_descriptors,
                        )
                        for description in category_descriptions
                        if (
                            XTEntity.supports_description(
                                device,
                                this_platform,
                                description,
                                True,
                                externally_managed_dpcodes,
                                COMPOUND_KEY,
                                hass_data.manager,
                            )
                            and (
                                definition := xt_get_default_definition(
                                    device,
                                    description=description,
                                    device_manager=hass_data.manager,
                                )
                            )
                        )
                    )
                    entities.extend(
                        XTSensorEntity.get_entity_instance(
                            description,
                            device,
                            hass_data.manager,
                            definition,
                            supported_descriptors,
                        )
                        for description in category_descriptions
                        if (
                            XTEntity.supports_description(
                                device,
                                this_platform,
                                description,
                                False,
                                externally_managed_dpcodes,
                                COMPOUND_KEY,
                                hass_data.manager,
                            )
                            and (
                                definition := xt_get_default_definition(
                                    device,
                                    description=description,
                                    device_manager=hass_data.manager,
                                )
                            )
                        )
                    )
        async_add_entities(entities)
        if restrict_dpcode is None:
            hass_data.manager.add_post_setup_callback(
                XTMultiManagerPostSetupCallbackPriority.PRIORITY_LAST,
                async_add_generic_entities,
                device_map,
            )

    hass_data.manager.register_device_descriptors(this_platform, supported_descriptors)
    async_discover_device([*hass_data.manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


# Some Bluetooth devices without a hub always report as offline in the Tuya cloud
# because connectivity is maintained locally via the app rather than through a hub.
# Listing them here forces HA to treat them as always available, so their last
# known state remains visible and updates are reflected when the app syncs data.
FORCE_ALWAYS_ONLINE_BY_DEVICE_ID: set[str] = {
    "bfa469yud5ajx1w8",  # SGS01
}
FORCE_ALWAYS_ONLINE_BY_PID: set[str] = {
    "gvygg3m8",          # SGS01 product ID
}
FORCE_ALWAYS_ONLINE_BY_CATEGORY: set[str] = {
    "zwjcy",             # SGS01 category
}


class XTSensorEntity(XTEntity, TuyaSensorEntity, RestoreSensor):  # type: ignore
    """XT Sensor Entity."""

    @dataclass
    class XTSensorConsumptionData:
        metadata: StatisticMetaData
        long_term_stats: list[StatisticData]
        short_term_stats: list[StatisticData]
        current_value: float

    entity_description: XTSensorEntityDescription
    _restored_data: SensorExtraStoredData | None = None

    def __init__(
        self,
        device: XTDevice,
        device_manager: MultiManager,
        description: XTSensorEntityDescription,
        definition: SensorDefinition,
        supported_descriptors: dict[str, tuple[XTSensorEntityDescription, ...]],
    ) -> None:
        """Init XT sensor."""
        super(XTSensorEntity, self).__init__(
            device=device,
            device_manager=device_manager,
            description=description,
            definition=definition,
        )
        self._attr_state_class = description.state_class
        super(XTEntity, self).__init__(
            device=device,
            device_manager=device_manager,  # type: ignore
            description=description,
            definition=definition,
        )

        self.device = device
        self.device_manager = device_manager
        self.entity_description = description  # type: ignore
        self.supported_descriptors = supported_descriptors
        self._currently_importing_statistics = False
        if self._attr_state_class in [
            SensorStateClass.TOTAL_INCREASING,
            SensorStateClass.TOTAL,
        ] and self.entity_description.device_class in [SensorDeviceClass.ENERGY]:
            all_energy_sensors: dict[str, list[XTSensorEntity]] = cast(
                dict[str, list[XTSensorEntity]],
                self.device_manager.get_general_property(
                    XTMultiManagerProperties.ENERGY_SENSOR, {}
                ),
            )
            if self.device.id not in all_energy_sensors:
                all_energy_sensors[self.device.id] = [self]
            else:
                all_energy_sensors[self.device.id].append(self)
            self.device_manager.set_general_property(
                XTMultiManagerProperties.ENERGY_SENSOR, all_energy_sensors
            )

        if isinstance(description, XTSensorEntityDescription):
            if description.recalculate_scale_for_percentage:
                device_manager.execute_device_entity_function(
                    XTDeviceEntityFunctions.RECALCULATE_PERCENT_SCALE,
                    device,
                    function_code=description.dpcode or description.key,
                    scale_threshold=description.recalculate_scale_for_percentage_threshold,
                )

    @property
    def available(self) -> bool:  # type: ignore[override]
        """Return True for devices that must be treated as always-online."""
        if (
            self.device.id in FORCE_ALWAYS_ONLINE_BY_DEVICE_ID
            or self.device.product_id in FORCE_ALWAYS_ONLINE_BY_PID
            or self.device.category in FORCE_ALWAYS_ONLINE_BY_CATEGORY
        ):
            return True
        return self.device.online

    def reset_value(self, _: datetime | None, manual_call: bool = False) -> None:
        if manual_call and self.cancel_reset_after_x_seconds is not None:
            self.cancel_reset_after_x_seconds()
        self.cancel_reset_after_x_seconds = None
        dpcode = getattr(self._dpcode_wrapper, "dpcode", None)
        if dpcode is None:
            return
        value = self.device.status.get(dpcode)
        default_value = get_default_value(
            self.get_dptype_from_dpcode_wrapper(wrapper=self._dpcode_wrapper)
        )
        if value is None or value == default_value:
            return
        self.device.status[dpcode] = default_value
        self.schedule_update_ha_state()

    def import_consumption_history(
        self, history: dict[str, dict[float, float]]
    ) -> None:
        if XTEventLoopProtector.hass is None:
            return
        registry = er.async_get(XTEventLoopProtector.hass)
        entry = registry.async_get(self.entity_id)
        if entry is None or entry.disabled:
            return
        for dpcode in history:
            all_dependant_dpcodes = self._get_dpcodes_based_on_dpcode(dpcode)
            if (
                self._get_description_dpcode(self.entity_description)
                in all_dependant_dpcodes
            ):
                consumption_data = self._get_consumption_stat_data(history[dpcode])
                if consumption_data is not None:
                    XTEventLoopProtector.execute_out_of_event_loop(
                        self._import_consumption_history, consumption_data
                    )
                    break

    def _get_consumption_stat_data(
        self, history: dict[float, float]
    ) -> XTSensorEntity.XTSensorConsumptionData | None:
        metadata = StatisticMetaData(
            has_mean=False,
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
            name=f"{self.entity_id} Consumption History",
            source="recorder",
            statistic_id=self.entity_id,
            unit_class=SensorDeviceClass.ENERGY,
            unit_of_measurement=self.unit_of_measurement,
        )
        long_term_stats: list[StatisticData] = []
        sum: float = 0.0
        last_timestamp: datetime | None = None
        start_of_this_hour = datetime.now(tz=UTC).replace(
            minute=0, second=0, microsecond=0
        )
        for timestamp, value in history.items():
            current_timestamp = datetime.fromtimestamp(timestamp, tz=UTC)
            should_reset_sum: bool = False
            if last_timestamp is not None:
                if (
                    self.entity_description.reset_daily
                    and last_timestamp.day != current_timestamp.day
                ):
                    should_reset_sum = True
                elif (
                    self.entity_description.reset_monthly
                    and last_timestamp.month != current_timestamp.month
                ):
                    should_reset_sum = True
                elif (
                    self.entity_description.reset_yearly
                    and last_timestamp.year != current_timestamp.year
                ):
                    should_reset_sum = True
            if should_reset_sum is True:
                sum = 0.0
            sum += value
            if current_timestamp < start_of_this_hour:
                long_term_stats.append(
                    StatisticData(
                        start=current_timestamp,
                        state=round(sum, 5),
                        sum=round(sum, 5),
                    )
                )
                last_timestamp = current_timestamp
        if len(long_term_stats) < 2:
            return None
        short_term_stats = [long_term_stats.pop(-1)]
        return XTSensorEntity.XTSensorConsumptionData(
            metadata=metadata,
            long_term_stats=long_term_stats,
            short_term_stats=short_term_stats,
            current_value=sum,
        )

    def _get_dpcode_descriptor(self, dpcode: str) -> XTSensorEntityDescription | None:
        category_descriptors = self.supported_descriptors.get(
            self.device.category, tuple()
        )
        for descriptor in category_descriptors:
            if self._get_description_dpcode(descriptor) == dpcode and isinstance(
                descriptor, XTSensorEntityDescription
            ):
                return descriptor
        return None

    def _get_dpcodes_based_on_dpcode(self, dpcode: str) -> list[str]:
        dpcodes = [dpcode]
        if descriptor := self._get_dpcode_descriptor(dpcode):
            for copy_dpcode in descriptor.vs_copy_to_state:
                copy_dpcodes = self._get_dpcodes_based_on_dpcode(copy_dpcode)
                dpcodes.extend(
                    dpcode for dpcode in copy_dpcodes if dpcode not in dpcodes
                )
            for copy_delta_dpcode in descriptor.vs_copy_delta_to_state:
                copy_delta_dpcodes = self._get_dpcodes_based_on_dpcode(
                    copy_delta_dpcode
                )
                dpcodes.extend(
                    dpcode for dpcode in copy_delta_dpcodes if dpcode not in dpcodes
                )
        return dpcodes

    async def _import_consumption_history(
        self, history: XTSensorEntity.XTSensorConsumptionData
    ) -> None:
        # First put the current value as base state, this prevents a bad short term stat from being created
        self.set_sensor_value(history.current_value)

        # Now mark the entity as unserviceable for now
        self._currently_importing_statistics = True
        self.device_manager.multi_device_listener.update_device(
            self.device, [self._get_description_dpcode(self.entity_description)]
        )

        # Clear and import the history
        if await self._clear_statistics() is True:
            await self._import_consumption_history_to_recorder(history)
        else:
            LOGGER.warning(f"Failed to clear existing statistics for {self.entity_id}")

        # Mark the entity as serviceable again
        self._currently_importing_statistics = False
        self.device_manager.multi_device_listener.update_device(
            self.device, [self._get_description_dpcode(self.entity_description)]
        )

    async def _import_consumption_history_to_recorder(
        self, history: XTSensorEntity.XTSensorConsumptionData
    ) -> None:
        """Import consumption history to recorder."""
        recorder = get_recorder_instance(self.hass)
        recorder.async_import_statistics(
            metadata=history.metadata, stats=history.long_term_stats, table=Statistics
        )
        recorder.async_import_statistics(
            metadata=history.metadata,
            stats=history.short_term_stats,
            table=StatisticsShortTerm,
        )
        await recorder.async_block_till_done()

    async def _clear_statistics(self) -> bool:
        """Clear statistics for this sensor."""
        done_event = asyncio.Event()

        recorder = get_recorder_instance(self.hass)

        def clear_statistics_done() -> None:
            self.hass.loop.call_soon_threadsafe(done_event.set)

        recorder.async_clear_statistics([self.entity_id], on_done=clear_statistics_done)
        try:
            async with asyncio.timeout(900):
                await done_event.wait()
                await recorder.async_block_till_done()
        except TimeoutError:
            return False
        return True

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        await super().async_added_to_hass()

        dpcode = getattr(self._dpcode_wrapper, "dpcode", None)
        if dpcode is None:
            return

        async def reset_status_daily(now: datetime) -> None:
            should_reset = False
            if self.entity_description.reset_daily:
                should_reset = True

            if self.entity_description.reset_monthly and now.day == 1:
                should_reset = True

            if self.entity_description.reset_yearly and now.day == 1 and now.month == 1:
                should_reset = True

            if should_reset:
                if device := self.device_manager.device_map.get(self.device.id, None):
                    if dpcode in device.status:
                        default_value = get_default_value(
                            self.get_dptype_from_dpcode_wrapper(
                                wrapper=self._dpcode_wrapper
                            )
                        )
                        if now.hour != 0 or now.minute != 0:
                            LOGGER.error(
                                f"Resetting {device.name}'s status {dpcode} to {default_value} at unexpected time",
                                stack_info=True,
                            )
                        else:
                            device.status[dpcode] = default_value
                            self.async_write_ha_state()

        if (
            self.entity_description.reset_daily
            or self.entity_description.reset_monthly
            or self.entity_description.reset_yearly
        ):
            self.async_on_remove(
                async_track_time_change(
                    self.hass, reset_status_daily, hour=0, minute=0, second=0
                )
            )

        if self.entity_description.restoredata:
            self._restored_data = await self.async_get_last_sensor_data()
            if (
                self._restored_data is not None
                and self._restored_data.native_value is not None
            ):
                if isinstance(self._restored_data.native_value, (str, int, float)):
                    self.set_sensor_value(self._restored_data.native_value)

        if self.entity_description.refresh_device_after_load:
            self.device_manager.multi_device_listener.update_device(
                self.device, [dpcode]
            )

    def set_sensor_value(self, value: StateType) -> None:
        dpcode = getattr(self._dpcode_wrapper, "dpcode", None)
        if dpcode is None:
            return
        scaled_value_back = self.scale_value_back(value)
        self.device_manager.device_watcher.report_message(
            self.device.id,
            f"Restoring value of {self.device.name}, original: {value}, converted back: {scaled_value_back}",
            XTDeviceWatcherCategory.PLATFORM_SENSOR,
            self.device,
            False,
        )
        self.device.status[dpcode] = scaled_value_back
        self.async_write_ha_state()

    def scale_value_back(self, value: StateType) -> StateType:
        type_information = self.get_type_information(wrapper=self._dpcode_wrapper)
        if isinstance(type_information, TuyaIntegerTypeInformation):
            if isinstance(value, (int, float)):
                return type_information.scale_value_back(value)
        return value

    @staticmethod
    def get_entity_instance(
        description: XTSensorEntityDescription,
        device: XTDevice,
        device_manager: MultiManager,
        definition: SensorDefinition,
        supported_descriptors: dict[str, tuple[XTSensorEntityDescription, ...]],
    ) -> XTSensorEntity:
        if hasattr(description, "get_entity_instance") and callable(
            getattr(description, "get_entity_instance")
        ):
            return description.get_entity_instance(
                device=device,
                device_manager=device_manager,
                description=description,
                definition=definition,
                supported_descriptors=supported_descriptors,
            )
        return XTSensorEntity(
            device=device,
            device_manager=device_manager,
            description=XTSensorEntityDescription(**description.__dict__),
            definition=definition,
            supported_descriptors=supported_descriptors,
        )

    @staticmethod
    def determine_state_class_from_dpcode_information(
        dpcode_information: XTDevice.XTDeviceDPCodeInformation | None,
        device_class: SensorDeviceClass | None,
    ) -> SensorStateClass | None:
        if dpcode_information is None:
            return None

        DEVICE_CLASS_MAPPING: dict[SensorDeviceClass, SensorStateClass] = {
            SensorDeviceClass.ENERGY: SensorStateClass.TOTAL_INCREASING,
            SensorDeviceClass.TEMPERATURE: SensorStateClass.MEASUREMENT,
        }
        if device_class is not None and device_class in DEVICE_CLASS_MAPPING:
            return DEVICE_CLASS_MAPPING[device_class]
        return None

    # Use custom native_value function
    @property
    def native_value(self) -> StateType:  # type: ignore
        if self._currently_importing_statistics:
            return None
        if self.entity_description.native_value is not None:
            value = self._dpcode_wrapper.read_device_status(self.device)
            value = self.entity_description.native_value(value)
        else:
            value = super().native_value
        return value
