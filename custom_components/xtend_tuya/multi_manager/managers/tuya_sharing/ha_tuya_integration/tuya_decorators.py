from __future__ import annotations

from .config_entry_handler import (
    XTHATuyaIntegrationConfigEntryManager,
)
from .....ha_tuya_integration.tuya_integration_imports import (
    tuya_integration,
    TuyaManager,
)
from ....shared.decorator import (
    XTDecorator,
)


def decorate_tuya_manager(
    tuya_manager: TuyaManager,
    ha_tuya_integration_config_manager: XTHATuyaIntegrationConfigEntryManager,
) -> list[XTDecorator]:
    return_list: list[XTDecorator] = []

    decorator, tuya_manager.refresh_mq = XTDecorator.get_decorator(
        base_object=tuya_manager,
        callback=ha_tuya_integration_config_manager.on_tuya_refresh_mq,
        method_name="refresh_mq",
    )
    return_list.append(decorator)

    decorator, tuya_manager.on_message = XTDecorator.get_decorator(
        base_object=tuya_manager,
        callback=ha_tuya_integration_config_manager.on_tuya_on_message,
        method_name="on_message",
        skip_call=True,
    )
    return_list.append(decorator)
    for device in tuya_manager.device_map.values():
        decorator, device.__setattr__ = XTDecorator.get_decorator(
            base_object=device,
            callback=ha_tuya_integration_config_manager.on_tuya_device_attribute_change,
            method_name="__setattr__",
        )
        return_list.append(decorator)

    return return_list


def decorate_tuya_integration(
    ha_tuya_integration_config_manager: XTHATuyaIntegrationConfigEntryManager,
) -> list[XTDecorator]:
    return_list: list[XTDecorator] = []

    decorator, tuya_integration.async_setup_entry = XTDecorator.get_async_decorator(
        base_object=tuya_integration,
        callback=ha_tuya_integration_config_manager.on_tuya_setup_entry,
        method_name="async_setup_entry",
    )
    return_list.append(decorator)

    decorator, tuya_integration.async_unload_entry = XTDecorator.get_async_decorator(
        base_object=tuya_integration,
        callback=ha_tuya_integration_config_manager.on_tuya_unload_entry,
        method_name="async_unload_entry",
    )
    return_list.append(decorator)

    decorator, tuya_integration.async_remove_entry = XTDecorator.get_async_decorator(
        base_object=tuya_integration,
        callback=ha_tuya_integration_config_manager.on_tuya_remove_entry,
        method_name="async_remove_entry",
    )
    return_list.append(decorator)
    return return_list


def undecorate_tuya_integration(decorators: list[XTDecorator]) -> None:
    for decorator in decorators:
        decorator.unwrap()
