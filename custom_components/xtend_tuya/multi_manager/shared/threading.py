from __future__ import annotations
import threading
import inspect
import asyncio
from functools import partial
from typing import Any
from homeassistant.core import (
    HomeAssistant,
    callback,
)
from ...const import (
    LOGGER,
)


class XTConcurrencyManager:

    hass: HomeAssistant | None = None

    def __init__(self, max_concurrency: int = 9999) -> None:
        self.coro_list: list = []
        self.max_concurrency = max_concurrency

    def add_coroutine(self, coroutine):
        self.coro_list.append(coroutine)

    async def gather(self):
        list_size = len(self.coro_list)
        i = 0
        while (i*self.max_concurrency < list_size):
            await asyncio.gather(*self.coro_list[i*self.max_concurrency : (i+1)*self.max_concurrency])
            i = i + 1


class XTEventLoopProtector:

    hass: HomeAssistant | None = None

    @staticmethod
    @callback
    def execute_out_of_event_loop(callback, *args, **kwargs) -> None:
        if XTEventLoopProtector.hass is None:
            LOGGER.error("protect_event_loop called without a HASS instance")
            return
        is_coroutine: bool = inspect.iscoroutinefunction(callback)
        if XTEventLoopProtector.hass.loop_thread_id != threading.get_ident():
            # Not in the event loop
            if is_coroutine:
                LOGGER.warning(f"Calling coroutine thread safe {callback}")
                asyncio.run_coroutine_threadsafe(
                    callback(*args, **kwargs), XTEventLoopProtector.hass.loop
                )
            else:
                callback(*args, **kwargs)
        else:
            # In the event loop
            if is_coroutine:
                XTEventLoopProtector.hass.async_create_task(callback(*args, **kwargs))
            else:
                if len(kwargs) > 0:
                    LOGGER.error(
                        "calling execute_out_of_event_loop with kwargs not supported",
                        stack_info=True,
                    )
                else:
                    XTEventLoopProtector.hass.async_add_executor_job(callback, *args)

    @staticmethod
    @callback
    async def execute_out_of_event_loop_and_return(callback, *args, **kwargs) -> Any:
        is_coroutine: bool = inspect.iscoroutinefunction(callback)
        if XTEventLoopProtector.hass is None:
            if is_coroutine:
                return await callback(*args)
            else:
                return callback(*args)
        
        if XTEventLoopProtector.hass.loop_thread_id != threading.get_ident():
            # Not in the event loop
            if is_coroutine:
                return await callback(*args)
            else:
                return callback(*args)
        else:
            # In the event loop
            if is_coroutine:
                LOGGER.warning("Non-sensical call to execute_out_of_event_loop_and_return", stack_info=True)
                return await callback(*args, **kwargs)
            else:
                LOGGER.debug("Calling execute_out_of_event_loop_and_return in watched case", stack_info=True)
                return await XTEventLoopProtector.hass.async_add_executor_job(
                    partial(callback, *args, **kwargs)
                )


class XTThread(threading.Thread):
    def __init__(self, callable, immediate_start: bool = False, *args, **kwargs):
        self.callable = callable
        self.immediate_start = immediate_start
        self.exception: Exception | None = None
        super().__init__(target=self.call_thread, args=args, kwargs=kwargs)

    def call_thread(self, *args, **kwargs):
        try:
            self.callable(*args, **kwargs)
        except Exception as e:
            self.exception = e

    def raise_exception_if_needed(self):
        if self.exception:
            raise self.exception


class XTThreadingManager:
    join_timeout: float = 0.05

    def __init__(self) -> None:
        self.thread_queue: list[XTThread] = []
        self.thread_active_list: list[XTThread] = []
        self.thread_finished_list: list[XTThread] = []
        self.max_concurrency: int | None = None

    def add_thread(self, callable, immediate_start: bool = False, *args, **kwargs):
        thread = XTThread(callable=callable, *args, **kwargs)
        self.thread_queue.append(thread)
        if immediate_start:
            thread.start()

    def start_all_threads(self, max_concurrency: int | None = None) -> None:
        self.max_concurrency = max_concurrency
        while (
            max_concurrency is None or len(self.thread_active_list) < max_concurrency
        ) and len(self.thread_queue) > 0:
            added_thread = self.thread_queue.pop(0)
            added_thread.start()
            self.thread_active_list.append(added_thread)

    def start_and_wait(self, max_concurrency: int | None = None) -> None:
        self.start_all_threads(max_concurrency)
        self.wait_for_all_threads()

    def clean_finished_threads(self):
        thread_active_list = self.thread_active_list
        at_least_one_thread_removed: bool = False
        for thread in thread_active_list:
            if thread.is_alive() is False:
                thread.join()
                self.thread_active_list.remove(thread)
                self.thread_finished_list.append(thread)
                at_least_one_thread_removed = True
        if at_least_one_thread_removed:
            self.start_all_threads(max_concurrency=self.max_concurrency)

    def wait_for_all_threads(self) -> None:
        while len(self.thread_active_list) > 0:
            self.clean_finished_threads()
            if len(self.thread_active_list) > 0:
                self.thread_active_list[0].join(timeout=self.join_timeout)
        for thread in self.thread_finished_list:
            thread.raise_exception_if_needed()
