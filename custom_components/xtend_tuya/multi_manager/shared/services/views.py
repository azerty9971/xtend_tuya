from __future__ import annotations

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

    def __init__(self, name: str, callback, requires_auth: bool = True) -> None:
        """Initialize a basic camera view."""
        self.name = "api:" + DOMAIN + ":" + name
        self.url = "/api/" + DOMAIN + "/" + name
        self.requires_auth = requires_auth
        self.callback = callback


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
        LOGGER.warning(f"Request: {request}")
        LOGGER.warning(f"Request headers: {request.headers}")
        LOGGER.warning(f"Request param: {request.query}")
        parameters: MultiMapping[str] = request.query
        for parameter in parameters:
            LOGGER.warning(f"parameter: {parameter} => {parameters[parameter]}")
