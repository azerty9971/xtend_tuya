from __future__ import annotations

from threading import Thread

from ...const import (
    LOGGER,
)

# class XTThreadingManager:

#     class XTThreadWrapper:
#         def __init__(self, callback, manager: XTThreadingManager) -> None:
#             self.callback = callback
#             self.manager = manager

#         def start(self, *args, **kwargs):
#             try:
#                 self.callback(*args, **kwargs)
#             except Exception as e:
#                 self.manager.report_exception(exception=e)

#     def __init__(self) -> None:
#         self.thread_queue: list[Thread] = []
#         self.thread_exception: list[Exception] = []
  
#     def add_thread(self, callable, immediate_start: bool = False, *args, **kwargs):
#         wrapper = XTThreadingManager.XTThreadWrapper(callback=callable, manager=self)
#         thread = Thread(target=wrapper.start, args=args, kwargs=kwargs)
#         self.thread_queue.append(thread)
#         if immediate_start:
#             thread.start()
  
#     def start_and_wait(self, max_concurrency: int | None = None) -> None:
#         self.start_all_threads(max_concurrency)
#         self.wait_for_all_threads()
#         self.raise_exception()

#     def start_all_threads(self, max_concurrency: int | None = None) -> None:
#         thread_list = self.thread_queue
#         if max_concurrency is not None:
#             thread_list = thread_list[:max_concurrency]
#         for thread in thread_list:
#             try:
#                 thread.start()
#             except Exception:
#                 #Thread was already started, ignore
#                 pass
#         if max_concurrency is not None:
#             self.wait_for_all_threads()
#             if len(thread_list) > max_concurrency:
#                 self.thread_queue = self.thread_queue[max_concurrency:]
#                 self.start_all_threads(max_concurrency=max_concurrency)
  
#     def wait_for_all_threads(self) -> None:
#         for thread in self.thread_queue:
#             try:
#                 thread.join()
#             except Exception:
#                 #Thread is not yet started, ignore
#                 pass

#     def report_exception(self, exception: Exception):
#         self.thread_exception.append(exception)

#     def raise_exception(self):
#         for exception in self.thread_exception:
#             LOGGER.warning(f"Thread exception: {exception}")
#         for exception in self.thread_exception:
#             raise exception

class XTThreadingManager:
    join_timeout: float = 0.05
    def __init__(self) -> None:
        self.thread_queue: list[Thread] = []
        self.thread_active_list: list[Thread] = []
        self.max_concurrency: int | None = None
    def add_thread(self, callable, immediate_start: bool = False, *args, **kwargs):
        thread = Thread(target=callable, args=args, kwargs=kwargs)
        self.thread_queue.append(thread)
        if immediate_start:
            thread.start()
    def start_all_threads(self, max_concurrency: int | None = None) -> None:
        self.max_concurrency = max_concurrency
        while (max_concurrency is None or len(self.thread_active_list) < max_concurrency) and len(self.thread_queue) > 0:
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
                at_least_one_thread_removed = True
        if at_least_one_thread_removed:
            self.start_all_threads(max_concurrency=self.max_concurrency)
    def wait_for_all_threads(self) -> None:
        while len(self.thread_active_list) > 0:
            self.clean_finished_threads()
            if len(self.thread_active_list) > 0:
                self.thread_active_list[0].join(timeout=self.join_timeout)