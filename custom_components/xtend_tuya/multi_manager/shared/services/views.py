from __future__ import annotations

from datetime import datetime, timedelta

from multidict import (
    MultiMapping,
)
import string
import random

from homeassistant.components.http import KEY_AUTHENTICATED, HomeAssistantView
from homeassistant.helpers.entity_component import EntityComponent, entity

from aiohttp import hdrs, web

from ....const import (
    LOGGER,  # noqa: F401
    DOMAIN,
)

class XTEventDataResultCache:
    def __init__(self, event_data, result, ttl: int = 60) -> None:
        self.event_data = event_data
        self.result = result
        self.valid_until = datetime.now() + timedelta(0, ttl)

class XTRequestCacheResult:
    def __init__(self, service_name: str) -> None:
        self.service_name = service_name
        self.cached_result: list[XTEventDataResultCache] = []
    
    def _clean_cache(self):
        current_time = datetime.now()
        for cache_entry in self.cached_result:
            if cache_entry.valid_until < current_time:
                self.cached_result.remove(cache_entry)

    def find_in_cache(self, event_data) -> any | None:
        self._clean_cache()
        for cache_entry in self.cached_result:
            if cache_entry.event_data == event_data:
                return cache_entry.result
        return None
    
    def append_to_cache(self, event_data, result, ttl: int = 60) -> None:
        self.cached_result.append(XTEventDataResultCache(event_data, result, ttl))

class XTEventData:
    @property
    def data(self) -> dict[str, any]:
        return self.query_params

    method: str = None
    query_params: dict[str, any] = None
    headers: dict[str, str] = None
    payload: str = None
    content_type: str = None
    session_id: str = None
    location: str = None

    def __init__(self) -> None:
        self.query_params = {}
        self.headers = {}
        self.session_id = self._id_generator()
    
    def __eq__(self, other: XTEventData) -> bool:
        return self.query_params == other.query_params and self.method == other.method and self.payload == other.payload

    def __repr__(self) -> str:
        return f"Method: {self.method} <=> Headers: {self.headers} <=> Content-Type: {self.content_type} <=> Query parameters: {self.query_params} <=> Payload: {self.payload}"

    def _id_generator(self, size=20, chars=string.ascii_lowercase + string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

class XTEntityView(HomeAssistantView):
    """Base EntityView."""

    requires_auth = True

    def __init__(self, component: EntityComponent, name: str, requires_auth: bool = True) -> None:
        """Initialize a basic camera view."""
        self.component = component
        self.name = "api:" + DOMAIN + ":" + name
        self.url = "/api/" + DOMAIN + "/" + name + "/{entity_id}"
        self.requires_auth = requires_auth


    async def get(self, request: web.Request, entity_id: str) -> web.StreamResponse:
        """Start a GET request."""
        entity: entity.Entity = self.component.get_entity(entity_id)
        if entity is None:
            raise web.HTTPNotFound

        authenticated = (
            request[KEY_AUTHENTICATED]
        )

        if self.requires_auth and not authenticated:
            # Attempt with invalid bearer token, raise unauthorized
            # so ban middleware can handle it.
            if hdrs.AUTHORIZATION in request.headers:
                raise web.HTTPUnauthorized
            # Invalid sigAuth or camera access token
            raise web.HTTPForbidden

        return await self.handle(request, entity)

    async def handle(self, request: web.Request, entity: entity.Entity) -> web.StreamResponse:
        """Handle the entity request."""
        raise NotImplementedError

class XTGeneralView(HomeAssistantView):
    requires_auth = True

    def __init__(self, name: str, callback, requires_auth: bool = True, use_cache: bool = True, cache_ttl: int = 60) -> None:
        """Initialize a basic camera view."""
        self.name = "api:" + DOMAIN + ":" + name
        self.url = "/api/" + DOMAIN + "/" + name
        #TEMPORARY FOR GO2RTC DEBUGGING
        self.requires_auth = False
        self.debug_requires_auth = requires_auth
        #END TEMPORARY FOR GO2RTC DEBUGGING
        self.callback = callback
        self.use_cache = use_cache
        self.cache: XTRequestCacheResult = XTRequestCacheResult(name)
        self.cache_ttl = cache_ttl


    async def get(self, request: web.Request) -> web.StreamResponse:
        """Start a GET request."""
        return await self.handle(request)

    async def post(self, request: web.Request) -> web.StreamResponse:
        """Start a POST request."""
        return await self.handle(request)

    async def delete(self, request: web.Request) -> web.StreamResponse:
        """Start a DELETE request."""
        return await self.handle(request)

    async def put(self, request: web.Request) -> web.StreamResponse:
        """Start a PUT request."""
        return await self.handle(request)
    
    async def patch(self, request: web.Request) -> web.StreamResponse:
        """Start a PATCH request."""
        return await self.handle(request)
    
    async def head(self, request: web.Request) -> web.StreamResponse:
        """Start a HEAD request."""
        return await self.handle(request)

    async def handle(self, request: web.Request) -> web.StreamResponse:
        """Verify authentication"""
        authenticated = (
            request[KEY_AUTHENTICATED]
        )

        if self.debug_requires_auth and not authenticated:
            # Attempt with invalid bearer token, raise unauthorized
            # so ban middleware can handle it.
            if hdrs.AUTHORIZATION in request.headers:
                raise web.HTTPUnauthorized
            # Invalid sigAuth or camera access token
            raise web.HTTPForbidden

        """Handle the entity request."""
        event_data: XTEventData = XTEventData()
        parameters: MultiMapping[str] = request.query
        event_data.method = request.method
        for parameter in parameters:
            event_data.query_params[parameter] = parameters[parameter]
        event_data.payload = request.content.read_nowait().decode()
        event_data.content_type = request.content_type
        for header in request.headers:
            event_data.headers[header] = request.headers[header]
        event_data.location = str(request.url)
        #event_data.headers = request.headers.__dict__
        query_use_cache = bool(event_data.query_params.get("use_cache", self.use_cache))
        query_cache_ttl = int(event_data.query_params.get("cache_ttl", self.cache_ttl))
        if query_use_cache:
            if result := self.cache.find_in_cache(event_data):
                return web.Response(text=result)
        response = await self.callback(event_data)
        if response is None:
            raise web.HTTPBadRequest
        if query_use_cache:
            self.cache.append_to_cache(event_data, response, query_cache_ttl)
        if isinstance(response, str):
            return web.Response(text=response)
        else:
            return response
