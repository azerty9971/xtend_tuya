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
    
    def start_and_wait(self):
        self.start_all_threads()
        self.wait_for_all_threads()

    def start_all_threads(self):
        for thread in self.thread_list:
            try:
                thread.start()
            except Exception:
                #Thread was already started, ignore
                pass
    
    def wait_for_all_threads(self):
        for thread in self.thread_list:
            thread.join()