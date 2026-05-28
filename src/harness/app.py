import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request

from src.core.config import load_config, parse_data_set
from src.harness.data_loader import DataLoader
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
    try:
        ctx = resolve_route(request, request.app.state.apps)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Internal server error") from exc
    return {
        "app": ctx.app_id,
        "env": ctx.env_id,
        "route": ctx.route_id,
        "params": ctx.params,
    }
