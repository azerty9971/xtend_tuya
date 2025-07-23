from __future__ import annotations
from threading import Thread

class XTThread(Thread):
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
