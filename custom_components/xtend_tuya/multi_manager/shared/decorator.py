from __future__ import annotations
import functools
from ...const import (
    LOGGER,
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
        if base_object:
            if hasattr(base_object, method_name):
                self.orig_method = getattr(base_object, method_name)
            else:
                LOGGER.warning(
                    "XTDecorator: Method %s not found in %s", method_name, base_object
                )

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
            return_val = None
            if self.callback is not None:
                return_val = self.callback(
                    # before_call, base_object, args... (don't use kwargs here as it breaks the logic)
                    True,
                    base_object,
                    *args,
                    **kwargs,
                )
            if self.orig_method is not None and self.skip_call is False:
                return_val = self.orig_method(*args, **kwargs)
            if self.callback is not None:
                return_val2 = self.callback(
                    # before_call, base_object, args... (don't use kwargs here as it breaks the logic)
                    False,
                    base_object,
                    *args,
                    **kwargs,
                )
                if return_val is None:
                    return_val = return_val2
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
