from __future__ import annotations
import functools
from .config_entry_handler import (
    XTHATuyaIntegrationConfigEntryManager,
)
from ....ha_tuya_integration.tuya_integration_imports import (
    tuya_integration,
    TuyaManager,
)
from ....const import (
    LOGGER,  # noqa: F401
)


class XTDecorator:
    def __init__(self) -> None:
        self.orig_object = None
        self.method_name: str | None = None
        self.func = None
        self.callback = None
        self.orig_method = None
        self.skip_call: bool = False

    def async_wrap(self, base_object, method_name, callback, skip_call: bool = False):
        self.orig_object = base_object
        self.callback = callback
        self.method_name = method_name
        self.skip_call = skip_call
        if base_object and hasattr(base_object, method_name):
            self.orig_method = getattr(base_object, method_name)

        @functools.wraps(base_object)
        async def wrapped(*args, **kwargs):
            if self.callback is not None:
                await callback(
                    # before_call, base_object, args... (don't use kwargs here as it breaks the logic)
                    True,
                    base_object,
                    *args,
                    **kwargs,
                )
            if self.orig_method is not None and self.skip_call is False:
                return_val = await self.orig_method(*args, **kwargs)
            else:
                return_val = None
            if self.callback is not None:
                await callback(
                    # before_call, base_object, args... (don't use kwargs here as it breaks the logic)
                    False,
                    base_object,
                    *args,
                    **kwargs,
                )
            return return_val

        self.func = wrapped
        return self.func

    def wrap(self, base_object, method_name, callback, skip_call: bool = False):
        self.orig_object = base_object
        self.callback = callback
        self.method_name = method_name
        self.skip_call = skip_call
        if base_object and hasattr(base_object, method_name):
            self.orig_method = getattr(base_object, method_name)

        @functools.wraps(base_object)
        def wrapped(*args, **kwargs):
            if self.callback is not None:
                self.callback(
                    # before_call, base_object, args... (don't use kwargs here as it breaks the logic)
                    True,
                    base_object,
                    *args,
                    **kwargs,
                )
            if self.orig_method is not None and self.skip_call is False:
                return_val = self.orig_method(*args, **kwargs)
            else:
                return_val = None
            if self.callback is not None:
                self.callback(
                    # before_call, base_object, args... (don't use kwargs here as it breaks the logic)
                    False,
                    base_object,
                    *args,
                    **kwargs,
                )
            return return_val

        self.func = wrapped
        return self.func

    def unwrap(self):
        if self.orig_object and self.orig_method and self.method_name:
            setattr(self.orig_object, self.method_name, self.orig_method)

    @staticmethod
    def get_async_decorator(
        base_object, callback, method_name: str, skip_call: bool = False
    ):
        decorator = XTDecorator()
        new_func = decorator.async_wrap(base_object, method_name, callback, skip_call)
        return decorator, new_func

    @staticmethod
    def get_decorator(base_object, callback, method_name: str, skip_call: bool = False):
        decorator = XTDecorator()
        new_func = decorator.wrap(base_object, method_name, callback, skip_call)
        return decorator, new_func


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
        callback=None,
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
