import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request

from src.core.config import parse_data_set
from src.harness.data_loader import DataLoader

_HARNESS_YAML = Path(__file__).parent.parent.parent / "harness.yaml"
_DATA_DIR = Path(__file__).parent.parent.parent / "data"


@asynccontextmanager
async def lifespan(app: FastAPI):
    dataset = os.environ.get("HARNESS_DATA_SET") or parse_data_set(_HARNESS_YAML)
    app.state.data_loader = DataLoader(_DATA_DIR, dataset)
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
)
async def catch_all(request: Request, path: str):
    return {
        "app": request.headers.get("x-harness-app"),
        "env": request.headers.get("x-harness-env"),
        "path": f"/{path}",
        "method": request.method,
    }
