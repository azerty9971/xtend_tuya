from __future__ import annotations

class XTAPICommonInterface:
    def __init__(self, api_name: str) -> None:
        self.api_name = api_name
        self.api_log: dict[str, int] = {}
    
    def register_api_call(self, method: str, path: str):
        full_path = f"{method} {path}"
        if full_path not in self.api_log:
            self.api_log[full_path] = 0
        self.api_log[full_path] += 1