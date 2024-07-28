import functools
from .const import (
    LOGGER
)
from tuya_sharing import (
    CustomerDevice,
    Manager,
    SharingDeviceListener,
    SharingTokenListener,
)

def report_called(func, after: bool):
    LOGGER.warning(f"{func.__name__} called (after = {after})")

def wrapper(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        report_called(func, False)
        return_val = func(*args, **kwargs)
        report_called(func, True)
        return return_val
    return wrapped
    
def decorate_tuya_manager(tuya_manager: Manager):
    tuya_manager.refresh_mq = wrapper(tuya_manager.refresh_mq)