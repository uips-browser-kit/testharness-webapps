from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request
from pydantic import BaseModel

from src.core.matcher import match
from src.core.models import App, NotServerVisible
from src.core.resolver import resolve


@dataclass
class RouteContext:
    app_id: str
    route_id: str
    env_id: str
    params: dict[str, str]


class ResolveRequest(BaseModel):
    app: str
    environment: str
    route: str
    parameters: dict[str, str] = {}
    query: dict[str, str] = {}


class MatchRequest(BaseModel):
    host: str
    path: str
    method: str = "GET"
    query: dict[str, str] = {}


def resolve_route(request: Request, apps: list[App]) -> RouteContext:
    """Match the incoming request to an app route. Raises HTTPException on failure."""
    host = request.headers.get("host", "").split(":")[0]
    path = request.url.path
    query = dict(request.query_params)

    result = match(host=host, path=path, query=query, apps=apps)
    if result is None:
        raise HTTPException(status_code=404, detail="No matching route")

    return RouteContext(
        app_id=result.app_id,
        route_id=result.route_id,
        env_id=result.env_id,
        params=result.params,
    )


def resolve_url(body: ResolveRequest, apps: list[App]) -> str:
    """Build the canonical URL for a given app/env/route/params combination."""
    app_obj = next((a for a in apps if a.id == body.app), None)
    if app_obj is None:
        raise HTTPException(status_code=404, detail=f"App '{body.app}' not found")
    if body.environment not in app_obj.environments:
        raise HTTPException(
            status_code=404, detail=f"Environment '{body.environment}' not found"
        )
    try:
        return resolve(
            app_obj, body.route, body.environment, {**body.parameters, **body.query}
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Route '{body.route}' not found")
    except NotServerVisible as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def match_request(body: MatchRequest, apps: list[App]) -> dict:
    """Match a host/path/query to an app route and return structured context."""
    result = match(host=body.host, path=body.path, query=body.query, apps=apps)
    if result is None:
        raise HTTPException(status_code=404, detail="No matching route")
    return {
        "app": result.app_id,
        "environment": result.env_id,
        "route": result.route_id,
        "parameters": result.params,
    }
