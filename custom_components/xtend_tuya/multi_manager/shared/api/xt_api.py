from __future__ import annotations
from typing import Any
from abc import abstractmethod



class XTAPIInterface:

    @abstractmethod
    def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None: ...


class XTAPIManager:

    def __init__(self) -> None:
        self.api_dict: dict[str, XTAPIInterface]

    def register_api(self, api_description: str, api_interface: XTAPIInterface) -> None:
        self.api_dict[api_description] = api_interface

    def get(
        self,
        api_description: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        return self.__request(
            api_description=api_description,
            method="GET",
            path=path,
            params=params,
            body=None,
        )

    def post(
        self,
        api_description: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        return self.__request(
            api_description=api_description,
            method="POST",
            path=path,
            params=params,
            body=body,
        )
    
    def put(
        self,
        api_description: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        return self.__request(
            api_description=api_description,
            method="PUT",
            path=path,
            params=params,
            body=body,
        )
    
    def delete(
        self,
        api_description: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        return self.__request(
            api_description=api_description,
            method="DELETE",
            path=path,
            params=params,
            body=None,
        )

    def __request(
        self,
        api_description: str,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if api := self.api_dict.get(api_description):
            return api.request(
                method=method,
                path=path,
                params=params,
                body=body,
            )
        return None
