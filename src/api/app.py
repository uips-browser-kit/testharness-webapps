import asyncio
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from src.api.metrics import CONTENT_TYPE_LATEST, generate_latest, record_request
from src.api.router import MatchRequest, ResolveRequest, match_request, resolve_route, resolve_url
from src.backend.data_loader import DataLoader
from src.backend.service import HarnessService, InMemoryChallengeStore
from src.core.config import load_config, parse_data_set
from src.core.models import Challenge, ErrorViewData, Fault, RecordNotFound, RouteContext, TemplateOnlyViewData
from src.frontend.renderer import render

_HARNESS_YAML = Path(__file__).parent.parent.parent / "harness.yaml"
_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_STATIC_DIR = Path(__file__).parent.parent.parent / "static"

_FAULT_TO_STATUS: dict[str, int] = {
    "server_error": 500,
    "unavailable": 503,
    "business_error": 409,
    "not_found": 404,
    "rate_limit": 429,
    "auth_error": 401,
    "forbidden": 403,
}

_STATUS_TITLES: dict[int, str] = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    406: "Not Acceptable",
    409: "Business Error",
    422: "Unprocessable",
    429: "Too Many Requests",
    500: "Server Error",
    503: "Service Unavailable",
}

_API_PREFIXES = ("/challenges", "/match", "/resolve", "/health", "/metrics", "/static")

_sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep


def _make_request_id(request: Request) -> str:
    return request.headers.get("x-request-id") or str(uuid.uuid4())


def _is_api_request(request: Request) -> bool:
    return request.url.path.startswith(_API_PREFIXES)


def _render_plain_error(error: ErrorViewData) -> str:
    retry = "<p>This error is temporary — you can retry the request.</p>" if error.retriable else ""
    return (
        "<!DOCTYPE html><html><head><meta charset=utf-8>"
        f"<title>{error.status_code} {error.title}</title>"
        "<style>body{font-family:sans-serif;padding:2rem;background:#002b36;color:#839496}"
        ".code{font-size:3rem;color:#dc322f;font-weight:700}</style></head>"
        f"<body><div class=code>{error.status_code}</div>"
        f"<h1>{error.title}</h1><p>{error.message}</p>{retry}"
        f"<p style='font-size:11px;color:#586e75'>Request ID: {error.request_id}</p>"
        "</body></html>"
    )


def _negotiate(request: Request) -> str | None:
    """Return 'html', 'json', or None (→ 406 Not Acceptable)."""
    fmt = request.query_params.get("format", "")
    if fmt == "json":
        return "json"
    if fmt == "html":
        return "html"

    accept = request.headers.get("accept", "")
    if not accept:
        return "html"

    best_html = -1.0
    best_json = -1.0
    has_any_supported = False

    for item in accept.split(","):
        parts = item.strip().split(";")
        media_type = parts[0].strip().lower()
        q = 1.0
        for p in parts[1:]:
            p = p.strip()
            if p.startswith("q="):
                try:
                    q = float(p[2:])
                except ValueError:
                    pass
        if media_type in ("text/html", "text/*"):
            best_html = max(best_html, q)
            has_any_supported = True
        elif media_type in ("application/json", "application/*"):
            best_json = max(best_json, q)
            has_any_supported = True
        elif media_type == "*/*":
            best_html = max(best_html, q)
            best_json = max(best_json, q)
            has_any_supported = True

    if not has_any_supported:
        return None  # 406

    return "json" if best_json > best_html else "html"


def _harness_index(apps: list) -> HTMLResponse:
    rows = []
    for app_obj in apps:
        home_nav = next((n for n in app_obj.nav if n.route_id in ("home", "dashboard")), None)
        for env_id, env in app_obj.environments.items():
            href = f"http://{env.host}{env.base_path.rstrip('/')}{home_nav.href if home_nav else '/'}"
            rows.append(
                f'<tr><td>{app_obj.vendor}</td><td>{app_obj.product}</td>'
                f'<td>{env_id}</td><td><a href="{href}">{env.host}</a></td></tr>'
            )
    table = "\n".join(rows)
    html = (
        "<!DOCTYPE html><html><head><meta charset=utf-8>"
        "<title>testharness-webapps</title>"
        '<link rel="stylesheet" href="/static/css/base.css"></head>'
        '<body><div class="shell" style="padding:2rem;">'
        "<h1 style='font-size:20px;font-weight:700;margin-bottom:1.5rem;'>testharness-webapps</h1>"
        "<table><thead><tr><th>Vendor</th><th>Product</th><th>Env</th><th>Host</th></tr></thead>"
        f"<tbody>{table}</tbody></table>"
        "</div></body></html>"
    )
    return HTMLResponse(content=html)


@asynccontextmanager
async def lifespan(app: FastAPI):
    dataset = os.environ.get("HARNESS_DATA_SET") or parse_data_set(_HARNESS_YAML)
    loader = DataLoader(_DATA_DIR, dataset)
    app.state.service = HarnessService(loader, InMemoryChallengeStore())
    app.state.apps = load_config(_HARNESS_YAML)
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = _make_request_id(request)
    retriable = exc.status_code in (503, 429)
    title = _STATUS_TITLES.get(exc.status_code, "Error")
    scope = getattr(request.state, "route_scope", "")
    support_code = f"{scope}:{exc.status_code}" if scope else ""
    error_data = ErrorViewData(
        status_code=exc.status_code,
        title=title,
        message=str(exc.detail),
        retriable=retriable,
        request_id=request_id,
        support_code=support_code,
    )

    if _is_api_request(request):
        return JSONResponse(status_code=exc.status_code, content=asdict(error_data))

    representation = _negotiate(request)
    if representation == "json":
        return JSONResponse(status_code=exc.status_code, content=asdict(error_data))

    # HTML — try per-app branded template, fall back to shared/error, then plain
    apps = getattr(request.app.state, "apps", [])
    host = request.headers.get("host", "").split(":")[0]
    matched_app = None
    matched_env_id = None
    for a in apps:
        for env_id, env_obj in a.environments.items():
            if env_obj.host == host:
                matched_app = a
                matched_env_id = env_id
                break
        if matched_app:
            break

    if matched_app:
        app_id = scope.split("/")[0] if scope else ""
        template_name = f"{app_id}/error" if app_id else "shared/error"
        ctx = RouteContext(app_id=matched_app.id, route_id="", env_id=matched_env_id, params={})
        try:
            html = render(matched_app, template_name, ctx, asdict(error_data))
            return HTMLResponse(status_code=exc.status_code, content=html)
        except Exception:
            try:
                html = render(matched_app, "shared/error", ctx, asdict(error_data))
                return HTMLResponse(status_code=exc.status_code, content=html)
            except Exception:
                pass

    return HTMLResponse(status_code=exc.status_code, content=_render_plain_error(error_data))


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
        fault = Fault(
            kind=fault_data["kind"],
            detail=fault_data.get("detail", "Simulated fault"),
            retriable=fault_data.get("retriable", False),
        )
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
    host = request.headers.get("host", "").split(":")[0]
    apps: list = request.app.state.apps

    # Redirect bare / to base_path/ for apps whose base_path is not /
    if request.url.path == "/":
        for app_obj in apps:
            for env_id, env in app_obj.environments.items():
                if env.host == host:
                    base = env.base_path.rstrip("/")
                    if base:
                        return RedirectResponse(url=base + "/", status_code=302)

    start = time.perf_counter()
    ctx = None
    status = 500
    try:
        ctx = resolve_route(request, apps)
        status = 200
        request.state.route_scope = f"{ctx.app_id}/{ctx.env_id}/{ctx.route_id}"
    except HTTPException as exc:
        status = exc.status_code
        if exc.status_code == 404 and not any(
            env.host == host
            for app_obj in apps
            for env in app_obj.environments.values()
        ):
            return _harness_index(apps)
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
    matched_app = next(a for a in apps if a.id == ctx.app_id)
    route = matched_app.route(ctx.route_id)

    service: HarnessService = request.app.state.service
    challenge = service.get_challenge((ctx.app_id, ctx.env_id, ctx.route_id))
    if challenge:
        if challenge.delay_ms > 0:
            await _sleeper(challenge.delay_ms / 1000)
        if challenge.fault:
            http_status = _FAULT_TO_STATUS.get(challenge.fault.kind, 500)
            raise HTTPException(status_code=http_status, detail=challenge.fault.detail)

    representation = _negotiate(request)
    if representation is None:
        raise HTTPException(status_code=406, detail="Not Acceptable")

    try:
        view = service.prepare_view(matched_app, route, ctx)
    except RecordNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if representation == "json":
        if view is not None:
            return asdict(view)
        return asdict(TemplateOnlyViewData(
            app_id=ctx.app_id, env_id=ctx.env_id,
            route_id=ctx.route_id, params=ctx.params,
        ))

    # HTML path — unchanged behaviour
    if not route.template:
        return {
            "app": ctx.app_id,
            "env": ctx.env_id,
            "route": ctx.route_id,
            "params": ctx.params,
        }

    extra = {k: v for k, v in asdict(view).items() if k != "kind"} if view else {}
    html = render(matched_app, route.template, ctx, extra)
    return HTMLResponse(content=html)
