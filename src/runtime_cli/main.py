from __future__ import annotations

import json
import sys
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import httpx
import typer

from src.backend.data_loader import DataLoader
from src.backend.service import HarnessService, InMemoryChallengeStore
from src.core.config import load_config, parse_data_set
from src.core.matcher import match
from src.core.models import Challenge, DetailViewData, Fault, RouteContext, TemplateOnlyViewData
from src.runtime_cli.formatters import print_json, print_view_table, view_to_dict

_HARNESS_YAML = Path(__file__).parent.parent.parent / "harness.yaml"
_DATA_DIR = Path(__file__).parent.parent.parent / "data"


class Format(str, Enum):
    json = "json"
    table = "table"


def _make_service() -> tuple[HarnessService, list]:
    dataset = parse_data_set(_HARNESS_YAML)
    loader = DataLoader(_DATA_DIR, dataset)
    apps = load_config(_HARNESS_YAML)
    service = HarnessService(loader, InMemoryChallengeStore())
    return service, apps


cli = typer.Typer(name="harness-cli", no_args_is_help=True, help="Runtime inspection for harness-webapps")
challenge_cli = typer.Typer(no_args_is_help=True, help="Inject or remove challenges on running API routes")
cli.add_typer(challenge_cli, name="challenge")


# ---------------------------------------------------------------------------
# route-match
# ---------------------------------------------------------------------------


@cli.command("route-match")
def route_match(
    app_id: Annotated[str, typer.Option("--app", help="App identifier (e.g. salesforce)")],
    env: Annotated[str, typer.Option("--env", help="Environment identifier (e.g. dev)")],
    path: Annotated[str, typer.Option("--path", help="URL path to match")],
    fmt: Annotated[Format, typer.Option("--format", help="Output format")] = Format.json,
    trace: Annotated[bool, typer.Option("--trace", help="Show each route tried and match/reject reason")] = False,
) -> None:
    """Match a URL path to a route for a given app/env."""
    _, apps = _make_service()
    app_obj = next((a for a in apps if a.id == app_id), None)
    if app_obj is None:
        typer.echo(f"Error: app '{app_id}' not found", err=True)
        raise typer.Exit(2)
    if env not in app_obj.environments:
        typer.echo(f"Error: environment '{env}' not found in app '{app_id}'", err=True)
        raise typer.Exit(2)

    env_obj = app_obj.environments[env]
    host = env_obj.host

    if trace:
        _trace_route_match(app_obj, path)
        return

    result = match(host=host, path=path, query={}, apps=apps)
    if result is None:
        typer.echo(f"No route matched path '{path}' for {app_id}/{env}", err=True)
        raise typer.Exit(1)

    data = {
        "app": result.app_id,
        "env": result.env_id,
        "route": result.route_id,
        "params": result.params,
    }
    print_json(data)


def _trace_route_match(app_obj, path: str) -> None:
    import urllib.parse  # noqa: PLC0415

    from src.core.matcher import _path_to_regex, _try_match  # noqa: PLC0415
    from src.core.models import PatternType  # noqa: PLC0415

    parsed = urllib.parse.urlparse(path)
    clean_path = parsed.path
    typer.echo(f"Tracing route match for path: {clean_path}")
    for route in app_obj.routes:
        typer.echo(f"  [{route.id}] pattern={route.pattern_type} path={route.path}")
        if route.pattern_type == PatternType.PATH:
            pattern, names = _path_to_regex(route.path)
            m = pattern.match(clean_path)
            if m is not None:
                params = dict(zip(names, m.groups()))
                typer.echo(f"    MATCH params={params}")
                return
            else:
                typer.echo("    no match")
        else:
            typer.echo("    skipped (query route — requires query params for full match)")
    typer.echo("  No route matched.")


# ---------------------------------------------------------------------------
# view-data
# ---------------------------------------------------------------------------


@cli.command("view-data")
def view_data(
    app_id: Annotated[str, typer.Option("--app", help="App identifier")],
    env: Annotated[str, typer.Option("--env", help="Environment identifier")],
    route: Annotated[str, typer.Option("--route", help="Route identifier")],
    param: Annotated[list[str], typer.Option("--param", help="Parameters as key=value (repeatable)")] = [],
    fmt: Annotated[Format, typer.Option("--format", help="Output format")] = Format.json,
    dump_context: Annotated[bool, typer.Option("--dump-context", help="Include full RouteContext in output")] = False,
) -> None:
    """Load and shape view data for a route (fully local, no server required)."""
    service, apps = _make_service()
    app_obj = next((a for a in apps if a.id == app_id), None)
    if app_obj is None:
        typer.echo(f"Error: app '{app_id}' not found", err=True)
        raise typer.Exit(2)
    if env not in app_obj.environments:
        typer.echo(f"Error: environment '{env}' not found in app '{app_id}'", err=True)
        raise typer.Exit(2)
    try:
        route_obj = app_obj.route(route)
    except KeyError:
        typer.echo(f"Error: route '{route}' not found in app '{app_id}'", err=True)
        raise typer.Exit(2)

    params: dict[str, str] = {}
    for p in param:
        if "=" not in p:
            typer.echo(f"Error: --param must be key=value, got: {p!r}", err=True)
            raise typer.Exit(2)
        k, v = p.split("=", 1)
        params[k] = v

    ctx = RouteContext(app_id=app_id, route_id=route, env_id=env, params=params)
    view = service.prepare_view(app_obj, route_obj, ctx)

    if view is None:
        view = TemplateOnlyViewData(app_id=app_id, env_id=env, route_id=route, params=params)
    data = view_to_dict(view)

    if dump_context:
        data = {"context": asdict(ctx), "view": data}

    if fmt == Format.table and view is not None:
        print_view_table(view)
    else:
        print_json(data)


# ---------------------------------------------------------------------------
# challenge set
# ---------------------------------------------------------------------------


@challenge_cli.command("set")
def challenge_set(
    app_id: Annotated[str, typer.Option("--app", help="App identifier")],
    env: Annotated[str, typer.Option("--env", help="Environment identifier")],
    route: Annotated[str, typer.Option("--route", help="Route identifier")],
    delay_ms: Annotated[int, typer.Option("--delay-ms", help="Delay in milliseconds")] = 0,
    fault_kind: Annotated[Optional[str], typer.Option("--fault-kind", help="Fault kind: server_error | unavailable | business_error | not_found")] = None,
    detail: Annotated[str, typer.Option("--detail", help="Fault detail message")] = "Simulated fault",
    api_url: Annotated[str, typer.Option("--api-url", help="Running API base URL")] = "http://localhost:8000",
    duration_s: Annotated[Optional[int], typer.Option("--duration-s", help="Auto-remove challenge after N seconds")] = None,
) -> None:
    """Inject a delay/fault challenge on the running API."""
    body: dict = {"delay_ms": delay_ms}
    if fault_kind:
        body["fault"] = {"kind": fault_kind, "detail": detail}

    try:
        r = httpx.post(f"{api_url}/challenges/{app_id}/{env}/{route}", json=body, timeout=5)
        r.raise_for_status()
    except httpx.HTTPError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    print_json(r.json())

    if duration_s is not None:
        import threading  # noqa: PLC0415

        def _auto_clear() -> None:
            import time  # noqa: PLC0415
            time.sleep(duration_s)
            try:
                httpx.delete(f"{api_url}/challenges/{app_id}/{env}/{route}", timeout=5)
            except httpx.HTTPError:
                pass

        t = threading.Thread(target=_auto_clear, daemon=True)
        t.start()
        typer.echo(f"Challenge will auto-clear in {duration_s}s (background thread started)")


# ---------------------------------------------------------------------------
# challenge clear
# ---------------------------------------------------------------------------


@challenge_cli.command("clear")
def challenge_clear(
    app_id: Annotated[str, typer.Option("--app", help="App identifier")],
    env: Annotated[str, typer.Option("--env", help="Environment identifier")],
    route: Annotated[str, typer.Option("--route", help="Route identifier")],
    api_url: Annotated[str, typer.Option("--api-url", help="Running API base URL")] = "http://localhost:8000",
) -> None:
    """Remove an active challenge from the running API."""
    try:
        r = httpx.delete(f"{api_url}/challenges/{app_id}/{env}/{route}", timeout=5)
        r.raise_for_status()
    except httpx.HTTPError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    print_json(r.json())


# ---------------------------------------------------------------------------
# challenge list
# ---------------------------------------------------------------------------


@challenge_cli.command("list")
def challenge_list(
    api_url: Annotated[str, typer.Option("--api-url", help="Running API base URL")] = "http://localhost:8000",
    fmt: Annotated[Format, typer.Option("--format", help="Output format")] = Format.json,
) -> None:
    """List all active challenges from the running API."""
    try:
        r = httpx.get(f"{api_url}/challenges", timeout=5)
        r.raise_for_status()
    except httpx.HTTPError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    data = r.json()
    if fmt == Format.table:
        from rich.console import Console  # noqa: PLC0415
        from rich.table import Table  # noqa: PLC0415
        console = Console()
        table = Table(title="Active Challenges", show_header=True)
        table.add_column("Key (app/env/route)")
        table.add_column("delay_ms")
        table.add_column("fault")
        for key, val in data.items():
            table.add_row(key, str(val.get("delay_ms", 0)), str(val.get("fault") or ""))
        console.print(table)
    else:
        print_json(data)
