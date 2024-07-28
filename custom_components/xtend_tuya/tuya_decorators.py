import functools

import homeassistant.components.tuya as tuya_integration

from .const import (
    LOGGER
)
from .multi_manager import (
    MultiManager
)
from tuya_sharing import (
    CustomerDevice,
    Manager,
    SharingDeviceListener,
    SharingTokenListener,
)

def async_wrapper(func, callback):
    @functools.wraps(func)
    async def wrapped(*args, **kwargs):
        callback(False, *args, **kwargs)
        return_val = await func(*args, **kwargs)
        callback(True, *args, **kwargs)
        return return_val
    return wrapped

def wrapper(func, callback):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        callback(False, *args, **kwargs)
        return_val = func(*args, **kwargs)
        callback(True, *args, **kwargs)
        return return_val
    return wrapped
    
def decorate_tuya_manager(tuya_manager: Manager, multi_manager: MultiManager):
    tuya_manager.refresh_mq = wrapper(tuya_manager.refresh_mq, multi_manager.on_tuya_refresh_mq)

def decorate_tuya_integration(multi_manager: MultiManager):
    tuya_integration.async_setup_entry = async_wrapper(tuya_integration.async_setup_entry, multi_manager.on_tuya_setup_entry)
    tuya_integration.async_unload_entry = async_wrapper(tuya_integration.async_unload_entry, multi_manager.on_tuya_unload_entry)
    tuya_integration.async_remove_entry = async_wrapper(tuya_integration.async_remove_entry, multi_manager.on_tuya_remove_entry)