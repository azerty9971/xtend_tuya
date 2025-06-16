from __future__ import annotations

from threading import Thread

from ...const import (
    LOGGER,
)

class XTThreadingManagerBase:
    def __init__(self) -> None:
        self.thread_queue: list[Thread] = []
    
    def add_thread(self, callable, immediate_start: bool = False, *args, **kwargs):
        thread = Thread(target=callable, args=args, kwargs=kwargs)
        self.thread_queue.append(thread)
        if immediate_start:
            thread.start()
    
    def start_and_wait(self, max_concurrency: int | None = None) -> None:
        self.start_all_threads(max_concurrency)
        self.wait_for_all_threads()

    def start_all_threads(self, max_concurrency: int | None = None) -> None:
        thread_list = self.thread_queue
        if max_concurrency is not None:
            thread_list = thread_list[:max_concurrency]
        for thread in thread_list:
            try:
                thread.start()
            except Exception:
                #Thread was already started, ignore
                pass
        if max_concurrency is not None:
            self.wait_for_all_threads()
            if len(thread_list) > max_concurrency:
                self.thread_queue = self.thread_queue[max_concurrency:]
                self.start_all_threads(max_concurrency=max_concurrency)
    
    def wait_for_all_threads(self) -> None:
        for thread in self.thread_queue:
            try:
                thread.join()
            except Exception:
                #Thread is not yet started, ignore
                pass

class XTThreadingManager(XTThreadingManagerBase):
    join_timeout: float = 0.05

    def __init__(self) -> None:
        super().__init__()
        self.thread_active_list: list[Thread] = []
        self.max_concurrency: int | None = None

    def start_all_threads(self, max_concurrency: int | None = None) -> None:
        if max_concurrency is None:
            return super().start_all_threads(max_concurrency=max_concurrency)
        
        self.max_concurrency = max_concurrency
        while len(self.thread_active_list) < max_concurrency and len(self.thread_queue) > 0:
            added_thread = self.thread_queue.pop(0)
            added_thread.start()
            self.thread_active_list.append(added_thread)

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