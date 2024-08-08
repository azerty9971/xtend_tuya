from __future__ import annotations

import functools

from .const import LOGGER

try:
    from ..tuya import (
        async_setup_entry  as tuya_integration_async_setup_entry,
        async_unload_entry as tuya_integration_async_unload_entry,
        async_remove_entry as tuya_integration_async_remove_entry
    )
except ImportError:
    LOGGER.warning("Loading regular Tuya module")
    from homeassistant.components.tuya import (
        async_setup_entry  as tuya_integration_async_setup_entry,
        async_unload_entry as tuya_integration_async_unload_entry,
        async_remove_entry as tuya_integration_async_remove_entry
    )

from .multi_manager import (
    MultiManager
)
from tuya_sharing import (
    Manager,
)

class XTDecorator:
    def __init__(self) -> None:
        self.orig_func = None
        self.func = None
        self.callback = None

    def async_wrapper(self, func, callback):
        self.orig_func = func
        self.callback = callback
        @functools.wraps(func)
        async def wrapped(*args, **kwargs):
            await callback(True, *args, **kwargs)
            return_val = await self.orig_func(*args, **kwargs)
            await callback(False, *args, **kwargs)
            return return_val
        self.func = wrapped
        return self.func

    def wrapper(self, func, callback):
        self.orig_func = func
        self.callback = callback
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            self.callback(True, *args, **kwargs)
            return_val = self.orig_func(*args, **kwargs)
            self.callback(False, *args, **kwargs)
            return return_val
        self.func = wrapped
        return self.func
    
    def get_async_decorator(func, callback):
        decorator = XTDecorator()
        new_func = decorator.async_wrapper(func, callback)
        return decorator, new_func
    
    def get_decorator(func, callback):
        decorator = XTDecorator()
        new_func = decorator.wrapper(func, callback)
        return decorator, new_func

def decorate_tuya_manager(tuya_manager: Manager, multi_manager: MultiManager) -> list[XTDecorator]:
    return_list : list[XTDecorator] = []

    decorator, tuya_manager.refresh_mq  = XTDecorator.get_decorator(tuya_manager.refresh_mq, multi_manager.on_tuya_refresh_mq)
    return_list.append(decorator)

    return return_list

def decorate_tuya_integration(multi_manager: MultiManager) -> list[XTDecorator]:
    return_list : list[XTDecorator] = []

    decorator, tuya_integration_async_setup_entry  = XTDecorator.get_async_decorator(tuya_integration_async_setup_entry, multi_manager.on_tuya_setup_entry)
    return_list.append(decorator)

    decorator, tuya_integration_async_unload_entry  = XTDecorator.get_async_decorator(tuya_integration_async_unload_entry, multi_manager.on_tuya_unload_entry)
    return_list.append(decorator)

    decorator, tuya_integration_async_remove_entry  = XTDecorator.get_async_decorator(tuya_integration_async_remove_entry, multi_manager.on_tuya_remove_entry)
    return_list.append(decorator)
    return return_list