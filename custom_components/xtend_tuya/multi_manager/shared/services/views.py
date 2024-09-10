from __future__ import annotations

from datetime import datetime, timedelta

from multidict import (
    MultiMapping,
)

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
        self.valid_until = datetime.now().time() + timedelta(0,ttl)

class XTRequestCacheResult:
    def __init__(self, service_name: str) -> None:
        self.service_name = service_name
        self.cached_result: list[XTEventDataResultCache] = []
    
    def _clean_cache(self):
        current_time = datetime.now().time()
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
    data: dict[str, any] = None

    def __init__(self) -> None:
        self.data = {}

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
        self.requires_auth = requires_auth
        self.callback = callback
        self.use_cache = use_cache
        self.cache: XTRequestCacheResult = XTRequestCacheResult(name)
        self.cache_ttl = cache_ttl


    async def get(self, request: web.Request) -> web.StreamResponse:
        """Start a GET request."""
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

        return await self.handle(request)

    async def handle(self, request: web.Request) -> web.StreamResponse:
        """Handle the entity request."""
        event_data: XTEventData = XTEventData()
        parameters: MultiMapping[str] = request.query
        for parameter in parameters:
            event_data.data[parameter] = parameters[parameter]
        if self.use_cache:
            if result := self.cache.find_in_cache(event_data):
                LOGGER.warning(f"Response from cache: {result}")
                return web.Response(text=result)
        response = await self.callback(event_data)
        LOGGER.warning(f"Response: {response}")
        if not response:
            raise web.HTTPBadRequest
        if self.use_cache:
            self.cache.append_to_cache(event_data, response, self.cache_ttl)
        return web.Response(text=response)
