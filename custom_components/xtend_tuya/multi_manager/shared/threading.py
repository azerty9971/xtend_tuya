from __future__ import annotations

from threading import Thread

class XTThreadingManager:
    def __init__(self) -> None:
        self.thread_list: list[Thread] = []
    
    def add_thread(self, callable, immediate_start: bool = False, *args, **kwargs):
        thread = Thread(target=callable, args=args, kwargs=kwargs)
        self.thread_list.append(thread)
        if immediate_start:
            thread.start()
    
    def start_and_wait(self, max_concurrency: int | None = None):
        self.start_all_threads(max_concurrency)
        self.wait_for_all_threads()

    def start_all_threads(self, max_concurrency: int | None = None):
        max_concurrency = 1
        thread_list = self.thread_list
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
                self.thread_list = thread_list[max_concurrency:]
                self.start_all_threads(max_concurrency=max_concurrency)
    
    def wait_for_all_threads(self):
        for thread in self.thread_list:
            try:
                thread.join()
            except Exception:
                #Thread is not yet started, ignore
                pass