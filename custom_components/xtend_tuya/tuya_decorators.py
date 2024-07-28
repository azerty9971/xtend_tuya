import functools
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

def wrapper(func, callback):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        callback(False)
        return_val = func(*args, **kwargs)
        callback(True)
        return return_val
    return wrapped
    
def decorate_tuya_manager(tuya_manager: Manager, multi_manager: MultiManager):
    tuya_manager.refresh_mq = wrapper(tuya_manager.refresh_mq, multi_manager.on_tuya_refresh_mq)