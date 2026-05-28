import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

from src.core.config import load_config, parse_data_set
from src.harness.data_loader import DataLoader
from src.harness.metrics import CONTENT_TYPE_LATEST, generate_latest, record_request
from src.harness.router import MatchRequest, ResolveRequest, match_request, resolve_route, resolve_url

_HARNESS_YAML = Path(__file__).parent.parent.parent / "harness.yaml"
_DATA_DIR = Path(__file__).parent.parent.parent / "data"


@asynccontextmanager
async def lifespan(app: FastAPI):
    dataset = os.environ.get("HARNESS_DATA_SET") or parse_data_set(_HARNESS_YAML)
    app.state.data_loader = DataLoader(_DATA_DIR, dataset)
    app.state.apps = load_config(_HARNESS_YAML)
    yield


app = FastAPI(lifespan=lifespan)


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
    return {
        "app": ctx.app_id,
        "env": ctx.env_id,
        "route": ctx.route_id,
        "params": ctx.params,
    }
