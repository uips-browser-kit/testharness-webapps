import asyncio
import os
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from src.api.metrics import CONTENT_TYPE_LATEST, generate_latest, record_request
from src.api.router import MatchRequest, ResolveRequest, match_request, resolve_route, resolve_url
from src.backend.data_loader import DataLoader
from src.backend.service import HarnessService, InMemoryChallengeStore
from src.core.config import load_config, parse_data_set
from src.core.models import Challenge, Fault
from src.frontend.renderer import render

_HARNESS_YAML = Path(__file__).parent.parent.parent / "harness.yaml"
_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_STATIC_DIR = Path(__file__).parent.parent.parent / "static"

_FAULT_TO_STATUS: dict[str, int] = {
    "server_error": 500,
    "unavailable": 503,
    "business_error": 409,
    "not_found": 404,
}

_sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep


@asynccontextmanager
async def lifespan(app: FastAPI):
    dataset = os.environ.get("HARNESS_DATA_SET") or parse_data_set(_HARNESS_YAML)
    loader = DataLoader(_DATA_DIR, dataset)
    app.state.service = HarnessService(loader, InMemoryChallengeStore())
    app.state.apps = load_config(_HARNESS_YAML)
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/resolve")
def resolve_endpoint(body: ResolveRequest, request: Request):
    url = resolve_url(body, request.app.state.apps)
    return {"url": url}


@app.post("/match")
def match_endpoint(body: MatchRequest, request: Request):
    return match_request(body, request.app.state.apps)


@app.post("/challenges/{app_id}/{env_id}/{route_id}")
def set_challenge(app_id: str, env_id: str, route_id: str, body: dict, request: Request):
    fault = None
    if fault_data := body.get("fault"):
        fault = Fault(kind=fault_data["kind"], detail=fault_data.get("detail", "Simulated fault"))
    challenge = Challenge(delay_ms=body.get("delay_ms", 0), fault=fault)
    request.app.state.service.set_challenge((app_id, env_id, route_id), challenge)
    return {"status": "set", "app": app_id, "env": env_id, "route": route_id}


@app.delete("/challenges/{app_id}/{env_id}/{route_id}")
def clear_challenge(app_id: str, env_id: str, route_id: str, request: Request):
    request.app.state.service.clear_challenge((app_id, env_id, route_id))
    return {"status": "cleared", "app": app_id, "env": env_id, "route": route_id}


@app.get("/challenges")
def list_challenges(request: Request):
    challenges = request.app.state.service.get_challenges()
    return {
        f"{k[0]}/{k[1]}/{k[2]}": {"delay_ms": v.delay_ms, "fault": asdict(v.fault) if v.fault else None}
        for k, v in challenges.items()
    }


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
)
async def catch_all(request: Request, path: str):
    start = time.perf_counter()
    ctx = None
    status = 500
    try:
        ctx = resolve_route(request, request.app.state.apps)
        status = 200
    except HTTPException as exc:
        status = exc.status_code
        raise
    except Exception as exc:
        status = 500
        raise HTTPException(status_code=500, detail="Internal server error") from exc
    finally:
        record_request(
            app_id=ctx.app_id if ctx else "unknown",
            env_id=ctx.env_id if ctx else "unknown",
            route_id=ctx.route_id if ctx else "unknown",
            status_code=status,
            duration=time.perf_counter() - start,
        )
    matched_app = next(a for a in request.app.state.apps if a.id == ctx.app_id)
    route = matched_app.route(ctx.route_id)

    service: HarnessService = request.app.state.service
    challenge = service.get_challenge((ctx.app_id, ctx.env_id, ctx.route_id))
    if challenge:
        if challenge.delay_ms > 0:
            await _sleeper(challenge.delay_ms / 1000)
        if challenge.fault:
            http_status = _FAULT_TO_STATUS.get(challenge.fault.kind, 500)
            raise HTTPException(status_code=http_status, detail=challenge.fault.detail)

    if not route.template:
        return {
            "app": ctx.app_id,
            "env": ctx.env_id,
            "route": ctx.route_id,
            "params": ctx.params,
        }

    view = service.prepare_view(matched_app, route, ctx)
    extra = {k: v for k, v in asdict(view).items() if k != "kind"} if view else {}

    html = render(matched_app, route.template, ctx, extra)
    return HTMLResponse(content=html)
