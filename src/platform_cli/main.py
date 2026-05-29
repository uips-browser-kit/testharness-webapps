from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Annotated, Optional

import httpx
import typer
import yaml

from src.core.config import ConfigError, load_config

_HARNESS_YAML = Path(__file__).parent.parent.parent / "harness.yaml"
_INFRA_DIR = Path(__file__).parent.parent.parent / "infra"
_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
_DATA_DIR = Path(__file__).parent.parent.parent / "data"

cli = typer.Typer(name="harness", no_args_is_help=True, help="Platform control-plane CLI")
idp_cli = typer.Typer(no_args_is_help=True, help="Keycloak IdP management")
cli.add_typer(idp_cli, name="idp")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_cli_config(harness_yaml: Path) -> dict:
    if not harness_yaml.exists():
        return {}
    raw = yaml.safe_load(harness_yaml.read_text(encoding="utf-8")) or {}
    return raw.get("cli", {})


def _load_raw_yaml(harness_yaml: Path) -> dict:
    if not harness_yaml.exists():
        return {}
    return yaml.safe_load(harness_yaml.read_text(encoding="utf-8")) or {}


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(content, encoding="utf-8")
    tmp.rename(path)


class _IdpVerifyFailed(Exception):
    def __init__(self, check: str, reason: str = ""):
        self.check = check
        self.reason = reason


def _get_admin_token(base_url: str, realm: str, user: str, pass_: str) -> str:
    url = f"{base_url}/realms/master/protocol/openid-connect/token"
    r = httpx.post(
        url,
        data={"client_id": "admin-cli", "grant_type": "password", "username": user, "password": pass_},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _verify_idp(
    base_url: str,
    realm: str,
    timeout_s: int,
    retry_interval_s: int,
    clients: list[str],
    client_secret: str | None,
    no_retry: bool,
    user: str = "admin",
    pass_: str = "admin",
) -> None:
    """Run three IdP checks; print [PASS]/[FAIL]/[SKIP]; raise _IdpVerifyFailed on failure."""
    deadline = time.monotonic() + timeout_s
    _passed: set[str] = set()

    def _attempt() -> None:
        # Check 1: OIDC discovery
        try:
            r = httpx.get(f"{base_url}/realms/{realm}/.well-known/openid-configuration", timeout=5)
            if r.status_code != 200:
                raise _IdpVerifyFailed("oidc-discovery", f"HTTP {r.status_code}")
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise _IdpVerifyFailed("oidc-discovery", str(exc)) from exc
        if "oidc-discovery" not in _passed:
            typer.echo("[PASS] oidc-discovery")
            _passed.add("oidc-discovery")

        # Check 2: clients present
        try:
            admin_token = _get_admin_token(base_url, realm, user, pass_)
            r2 = httpx.get(
                f"{base_url}/admin/realms/{realm}/clients",
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=10,
            )
            if r2.status_code != 200:
                raise _IdpVerifyFailed("clients-present", f"HTTP {r2.status_code}")
            existing = {c["clientId"] for c in r2.json()}
            missing = [c for c in clients if c not in existing]
            if missing:
                raise _IdpVerifyFailed("clients-present", f"missing: {missing}")
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise _IdpVerifyFailed("clients-present", str(exc)) from exc
        if "clients-present" not in _passed:
            typer.echo("[PASS] clients-present")
            _passed.add("clients-present")

        # Check 3: token acquisition (optional)
        if not client_secret:
            if "token-check" not in _passed:
                typer.echo("[SKIP] token-check (no --client-secret supplied)")
                _passed.add("token-check")
            return
        try:
            first_client = clients[0] if clients else "browser-client"
            r3 = httpx.post(
                f"{base_url}/realms/{realm}/protocol/openid-connect/token",
                data={
                    "client_id": first_client,
                    "client_secret": client_secret,
                    "grant_type": "client_credentials",
                },
                timeout=10,
            )
            if r3.status_code in (400, 401):
                raise _IdpVerifyFailed("token-check", f"HTTP {r3.status_code} (wrong secret?)")
            if r3.status_code != 200:
                raise _IdpVerifyFailed("token-check", f"HTTP {r3.status_code}")
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise _IdpVerifyFailed("token-check", str(exc)) from exc
        if "token-check" not in _passed:
            typer.echo("[PASS] token-check")
            _passed.add("token-check")

    while True:
        try:
            _attempt()
            return
        except _IdpVerifyFailed as exc:
            if no_retry or time.monotonic() >= deadline:
                typer.echo(f"[FAIL] {exc.check}: {exc.reason or 'check failed'}")
                raise
            time.sleep(retry_interval_s)


# ---------------------------------------------------------------------------
# harness validate
# ---------------------------------------------------------------------------


@cli.command("validate")
def validate(
    config: Annotated[Path, typer.Option("--config", help="Path to harness.yaml")] = _HARNESS_YAML,
    check_templates: Annotated[bool, typer.Option("--check-templates", help="Verify template files exist")] = False,
    check_data_files: Annotated[bool, typer.Option("--check-data-files", help="Verify data JSON files exist")] = False,
) -> None:
    """Validate harness.yaml structure and optional file references."""
    if not config.exists():
        typer.echo(f"Error: config not found: {config}", err=True)
        raise typer.Exit(2)

    cfg = _load_cli_config(config)
    validate_cfg = cfg.get("validate", {})
    if validate_cfg.get("check_templates"):
        check_templates = True
    if validate_cfg.get("check_data_files"):
        check_data_files = True

    try:
        apps = load_config(config)
    except ConfigError as exc:
        typer.echo(f"ERROR {exc}", err=True)
        raise typer.Exit(1)

    errors: list[str] = []
    repo_root = config.parent

    # Duplicate host names across all environments
    seen_hosts: dict[str, str] = {}
    for app in apps:
        for env_id, env in app.environments.items():
            key = f"{app.id}/{env_id}"
            if env.host in seen_hosts:
                errors.append(f"[duplicate-host] {env.host!r} used by {seen_hosts[env.host]!r} and {key!r}")
            else:
                seen_hosts[env.host] = key

    # Duplicate route IDs within each app
    for app in apps:
        seen_route_ids: set[str] = set()
        for route in app.routes:
            if route.id in seen_route_ids:
                errors.append(f"[duplicate-route-id] app {app.id!r} has duplicate route id {route.id!r}")
            seen_route_ids.add(route.id)

    # Optional file existence checks
    if check_templates:
        for app in apps:
            for route in app.routes:
                if not route.template:
                    continue
                if "/" in route.template:
                    typer.echo(f"WARN [unchecked-pattern] {route.template}")
                    continue
                tpl_path = repo_root / "templates" / app.id / f"{route.template}.html"
                if not tpl_path.exists():
                    errors.append(f"[missing-template] {tpl_path.relative_to(repo_root)}")

    if check_data_files:
        for app in apps:
            for route in app.routes:
                if not route.data_entity:
                    continue
                data_path = repo_root / "data" / "default" / app.id / f"{route.data_entity}.json"
                if not data_path.exists():
                    errors.append(f"[missing-data-file] {data_path.relative_to(repo_root)}")

    if errors:
        for err in errors:
            typer.echo(f"ERROR {err}", err=True)
        raise typer.Exit(1)

    route_count = sum(len(a.routes) for a in apps)
    typer.echo(f"OK  {len(apps)} apps, {route_count} routes validated")


# ---------------------------------------------------------------------------
# harness generate-caddy
# ---------------------------------------------------------------------------


@cli.command("generate-caddy")
def generate_caddy(
    config: Annotated[Path, typer.Option("--config", help="Path to harness.yaml")] = _HARNESS_YAML,
    out: Annotated[Optional[Path], typer.Option("--out", help="Output Caddyfile path")] = None,
    harness_host: Annotated[Optional[str], typer.Option("--harness-host")] = None,
    idp_host: Annotated[Optional[str], typer.Option("--idp-host")] = None,
    metrics_host: Annotated[Optional[str], typer.Option("--metrics-host")] = None,
) -> None:
    """Generate Caddy reverse-proxy config from harness.yaml."""
    if not config.exists():
        typer.echo(f"Error: config not found: {config}", err=True)
        raise typer.Exit(2)

    cfg = _load_cli_config(config)
    caddy_cfg = cfg.get("caddy", {})

    harness_host = harness_host or caddy_cfg.get("harness_host", "harness.local")
    idp_host = idp_host or caddy_cfg.get("idp_host", "idp.local")
    metrics_host = metrics_host or caddy_cfg.get("metrics_host", "metrics.local")

    run_cfg = cfg.get("run", {})
    out = out or Path(caddy_cfg.get("out", str(_INFRA_DIR / "caddy" / "Caddyfile")))

    try:
        apps = load_config(config)
    except ConfigError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    lines: list[str] = []
    lines.append("{\n\tadmin off\n}\n")

    lines.append(f"# Platform management\nhttp://{harness_host} {{\n"
                 f"\trequest_header -X-Harness-App\n\trequest_header -X-Harness-Env\n"
                 f"\t@no_reqid not header X-Request-ID *\n"
                 f"\trequest_header @no_reqid X-Request-ID {{uuid}}\n"
                 f"\treverse_proxy harness:8000\n}}\n")

    lines.append(f"# Identity provider\nhttp://{idp_host} {{\n"
                 f"\treverse_proxy idp:8080\n}}\n")

    lines.append(f"# Prometheus UI\nhttp://{metrics_host} {{\n"
                 f"\treverse_proxy metrics:9090\n}}\n")

    for app in apps:
        for env_id, env in app.environments.items():
            lines.append(
                f"# {app.vendor} — {env_id}\n"
                f"http://{env.host} {{\n"
                f"\trequest_header -X-Harness-App\n"
                f"\trequest_header -X-Harness-Env\n"
                f"\trequest_header X-Harness-App \"{app.id}\"\n"
                f"\trequest_header X-Harness-Env \"{env_id}\"\n"
                f"\t@no_reqid not header X-Request-ID *\n"
                f"\trequest_header @no_reqid X-Request-ID {{uuid}}\n"
                f"\treverse_proxy harness:8000\n"
                f"}}\n"
            )

    content = "\n\n".join(b.rstrip("\n") for b in lines) + "\n"
    try:
        _atomic_write(out, content)
    except OSError as exc:
        typer.echo(f"Error writing {out}: {exc}", err=True)
        raise typer.Exit(4)

    typer.echo(f"Written: {out}")


# ---------------------------------------------------------------------------
# harness generate-prometheus
# ---------------------------------------------------------------------------


@cli.command("generate-prometheus")
def generate_prometheus(
    config: Annotated[Path, typer.Option("--config", help="Path to harness.yaml")] = _HARNESS_YAML,
    out: Annotated[Optional[Path], typer.Option("--out", help="Output prometheus.yml path")] = None,
    target: Annotated[Optional[str], typer.Option("--target", help="Scrape target")] = None,
) -> None:
    """Generate Prometheus scrape config from harness.yaml."""
    if not config.exists():
        typer.echo(f"Error: config not found: {config}", err=True)
        raise typer.Exit(2)

    cfg = _load_cli_config(config)
    prom_cfg = cfg.get("prometheus", {})
    raw = _load_raw_yaml(config)

    scrape_interval = raw.get("prometheus", {}).get("scrape_interval", "15s") if isinstance(raw.get("prometheus"), dict) else "15s"
    target = target or prom_cfg.get("target", "harness:8000")
    out = out or Path(prom_cfg.get("out", str(_INFRA_DIR / "prometheus" / "prometheus.yml")))

    content = (
        f"global:\n"
        f"  scrape_interval: {scrape_interval}\n"
        f"\n"
        f"scrape_configs:\n"
        f"  - job_name: harness\n"
        f"    static_configs:\n"
        f'      - targets: ["{target}"]\n'
    )

    try:
        _atomic_write(out, content)
    except OSError as exc:
        typer.echo(f"Error writing {out}: {exc}", err=True)
        raise typer.Exit(4)

    typer.echo(f"Written: {out}")


# ---------------------------------------------------------------------------
# harness seed
# ---------------------------------------------------------------------------


@cli.command("seed")
def seed(
    set_name: Annotated[str, typer.Option("--set", help="Data set name")] = "",
    seed_val: Annotated[Optional[int], typer.Option("--seed", help="Faker seed")] = None,
    count: Annotated[Optional[int], typer.Option("--count", help="Records per entity")] = None,
    app: Annotated[Optional[str], typer.Option("--app", help="Seed only this app id")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print command without executing")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", help="Echo stdout/stderr on success")] = False,
    config: Annotated[Path, typer.Option("--config", help="Path to harness.yaml")] = _HARNESS_YAML,
) -> None:
    """Seed data by delegating to scripts/generate_data.py."""
    cfg = _load_cli_config(config)
    seed_cfg = cfg.get("seed", {})

    set_name = set_name or seed_cfg.get("set", "default")
    if count is None:
        count = seed_cfg.get("count", 20)
    if seed_val is None:
        seed_val = seed_cfg.get("seed")

    script = _SCRIPTS_DIR / "generate_data.py"
    if not script.exists():
        typer.echo(f"Error: script not found: {script}", err=True)
        raise typer.Exit(2)

    cmd = ["uv", "run", "python", str(script), "--set", set_name, "--count", str(count)]
    if seed_val is not None:
        cmd += ["--seed", str(seed_val)]
    if app:
        cmd += ["--app", app]

    if dry_run:
        typer.echo("Would run: " + " ".join(cmd))
        return

    result = subprocess.run(cmd, capture_output=True, text=True)
    if verbose or result.returncode != 0:
        if result.stdout:
            typer.echo(result.stdout.rstrip())
        if result.stderr:
            typer.echo(result.stderr.rstrip(), err=True)
    if result.returncode != 0:
        raise typer.Exit(4)


# ---------------------------------------------------------------------------
# harness idp export
# ---------------------------------------------------------------------------


@idp_cli.command("export")
def idp_export(
    keycloak_url: Annotated[str, typer.Option("--keycloak-url")] = "",
    realm: Annotated[str, typer.Option("--realm")] = "",
    out: Annotated[Optional[Path], typer.Option("--out")] = None,
    config: Annotated[Path, typer.Option("--config")] = _HARNESS_YAML,
) -> None:
    """Export a Keycloak realm to JSON."""
    cfg = _load_cli_config(config).get("idp", {})
    keycloak_url = keycloak_url or cfg.get("base_url", "http://idp.local")
    realm = realm or cfg.get("realm", "harness")
    out = out or Path(cfg.get("export_out", str(_INFRA_DIR / "keycloak" / f"{realm}-realm.json")))

    user = os.environ.get(cfg.get("admin_user_env", "KEYCLOAK_ADMIN_USER"), "admin")
    pass_ = os.environ.get(cfg.get("admin_pass_env", "KEYCLOAK_ADMIN_PASS"), "admin")

    try:
        token = _get_admin_token(keycloak_url, realm, user, pass_)
        r = httpx.get(
            f"{keycloak_url}/admin/realms/{realm}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        typer.echo(f"Error: API error {exc.response.status_code}", err=True)
        raise typer.Exit(1)
    except httpx.RequestError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(r.json(), indent=2), encoding="utf-8")
    typer.echo(f"Exported realm {realm!r} to {out}")


# ---------------------------------------------------------------------------
# harness idp import
# ---------------------------------------------------------------------------


@idp_cli.command("import")
def idp_import(
    src: Annotated[Optional[Path], typer.Option("--src")] = None,
    keycloak_url: Annotated[str, typer.Option("--keycloak-url")] = "",
    realm: Annotated[str, typer.Option("--realm")] = "",
    config: Annotated[Path, typer.Option("--config")] = _HARNESS_YAML,
) -> None:
    """Import a Keycloak realm from JSON (idempotent: creates or full-overwrites)."""
    cfg = _load_cli_config(config).get("idp", {})
    keycloak_url = keycloak_url or cfg.get("base_url", "http://idp.local")
    realm = realm or cfg.get("realm", "harness")
    src = src or Path(cfg.get("export_out", str(_INFRA_DIR / "keycloak" / f"{realm}-realm.json")))

    if not src.exists():
        typer.echo(f"Error: source file not found: {src}", err=True)
        raise typer.Exit(2)

    user = os.environ.get(cfg.get("admin_user_env", "KEYCLOAK_ADMIN_USER"), "admin")
    pass_ = os.environ.get(cfg.get("admin_pass_env", "KEYCLOAK_ADMIN_PASS"), "admin")
    realm_json = json.loads(src.read_text(encoding="utf-8"))

    try:
        token = _get_admin_token(keycloak_url, realm, user, pass_)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        r = httpx.post(f"{keycloak_url}/admin/realms", headers=headers, json=realm_json, timeout=30)
        if r.status_code == 201:
            typer.echo(f"Realm {realm!r} created")
            return
        if r.status_code == 409:
            r2 = httpx.put(
                f"{keycloak_url}/admin/realms/{realm}",
                headers=headers,
                json=realm_json,
                timeout=30,
            )
            if r2.status_code == 204:
                typer.echo(f"Realm {realm!r} updated (idempotent)")
                return
            typer.echo(f"Error: PUT /admin/realms/{realm} returned {r2.status_code}", err=True)
            raise typer.Exit(1)
        typer.echo(f"Error: POST /admin/realms returned {r.status_code}: {r.text[:200]}", err=True)
        raise typer.Exit(1)
    except httpx.RequestError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# harness idp verify
# ---------------------------------------------------------------------------


@idp_cli.command("verify")
def idp_verify(
    keycloak_url: Annotated[str, typer.Option("--keycloak-url")] = "",
    realm: Annotated[str, typer.Option("--realm")] = "",
    timeout: Annotated[Optional[int], typer.Option("--timeout")] = None,
    retry_interval: Annotated[Optional[int], typer.Option("--retry-interval")] = None,
    no_retry: Annotated[bool, typer.Option("--no-retry")] = False,
    client: Annotated[list[str], typer.Option("--client")] = [],
    client_secret: Annotated[Optional[str], typer.Option("--client-secret")] = None,
    config: Annotated[Path, typer.Option("--config")] = _HARNESS_YAML,
) -> None:
    """Verify Keycloak IdP readiness (OIDC discovery, clients, optional token check)."""
    cfg = _load_cli_config(config).get("idp", {})
    keycloak_url = keycloak_url or cfg.get("base_url", "http://idp.local")
    realm = realm or cfg.get("realm", "harness")
    timeout = timeout if timeout is not None else cfg.get("retry_timeout", 60)
    retry_interval = retry_interval if retry_interval is not None else cfg.get("retry_interval", 1)
    clients = list(client) or cfg.get("clients", ["browser-client", "service-client"])
    user = os.environ.get(cfg.get("admin_user_env", "KEYCLOAK_ADMIN_USER"), "admin")
    pass_ = os.environ.get(cfg.get("admin_pass_env", "KEYCLOAK_ADMIN_PASS"), "admin")

    try:
        _verify_idp(keycloak_url, realm, timeout, retry_interval, clients, client_secret, no_retry, user, pass_)
    except _IdpVerifyFailed:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# harness run
# ---------------------------------------------------------------------------


@cli.command("run")
def run(
    compose_file: Annotated[Optional[Path], typer.Option("--compose-file")] = None,
    project_name: Annotated[Optional[str], typer.Option("--project-name")] = None,
    no_build: Annotated[bool, typer.Option("--no-build")] = False,
    health_url: Annotated[Optional[str], typer.Option("--health-url")] = None,
    health_timeout: Annotated[Optional[int], typer.Option("--health-timeout")] = None,
    health_interval: Annotated[Optional[int], typer.Option("--health-interval")] = None,
    idp_timeout: Annotated[Optional[int], typer.Option("--idp-timeout")] = None,
    idp_client: Annotated[list[str], typer.Option("--idp-client")] = [],
    skip_idp_verify: Annotated[bool, typer.Option("--skip-idp-verify")] = False,
    config: Annotated[Path, typer.Option("--config")] = _HARNESS_YAML,
) -> None:
    """Start the platform: docker compose up → health check → IdP readiness."""
    cfg = _load_cli_config(config)
    run_cfg = cfg.get("run", {})
    idp_cfg = cfg.get("idp", {})

    compose_file = compose_file or Path(run_cfg.get("compose_file", str(_INFRA_DIR / "docker-compose.yml")))
    health_url = health_url if health_url is not None else run_cfg.get("health_url", "http://localhost:8000/health")
    health_timeout = health_timeout if health_timeout is not None else run_cfg.get("health_timeout", 30)
    health_interval = health_interval if health_interval is not None else run_cfg.get("health_interval", 2)
    idp_timeout = idp_timeout if idp_timeout is not None else idp_cfg.get("retry_timeout", 60)
    idp_verify_enabled = not skip_idp_verify and run_cfg.get("idp_verify", True)

    if not compose_file.exists():
        typer.echo(f"Error: compose file not found: {compose_file}", err=True)
        raise typer.Exit(2)

    # Phase 1 — Docker Compose
    typer.echo("Phase 1: docker compose up")
    cmd = ["docker", "compose"]
    if project_name:
        cmd += ["-p", project_name]
    cmd += ["-f", str(compose_file), "up"]
    if not no_build:
        cmd.append("--build")
    cmd.append("-d")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        typer.echo("Error: docker not found on PATH", err=True)
        raise typer.Exit(3)

    if result.returncode != 0:
        if result.stderr:
            typer.echo(result.stderr.rstrip(), err=True)
        raise typer.Exit(3)

    # Phase 2 — Harness health
    typer.echo(f"Phase 2: waiting for harness at {health_url}")
    deadline = time.monotonic() + health_timeout
    healthy = False
    while time.monotonic() < deadline:
        try:
            r = httpx.get(health_url, timeout=3)
            if r.status_code == 200:
                healthy = True
                break
        except httpx.RequestError:
            pass
        time.sleep(health_interval)

    if not healthy:
        typer.echo(f"Error: harness did not become healthy after {health_timeout}s", err=True)
        raise typer.Exit(3)

    # Phase 3 — IdP readiness
    if idp_verify_enabled:
        typer.echo("Phase 3: verifying IdP")
        keycloak_url = idp_cfg.get("base_url", "http://idp.local")
        realm = idp_cfg.get("realm", "harness")
        clients = list(idp_client) or idp_cfg.get("clients", ["browser-client", "service-client"])
        retry_interval = idp_cfg.get("retry_interval", 1)
        user = os.environ.get(idp_cfg.get("admin_user_env", "KEYCLOAK_ADMIN_USER"), "admin")
        pass_ = os.environ.get(idp_cfg.get("admin_pass_env", "KEYCLOAK_ADMIN_PASS"), "admin")
        try:
            _verify_idp(keycloak_url, realm, idp_timeout, retry_interval, clients, None, False, user, pass_)
        except _IdpVerifyFailed as exc:
            typer.echo(f"Error: Keycloak not ready: {exc.check}", err=True)
            raise typer.Exit(3)
        typer.echo("Phase 3: IdP ready")

    cfg_caddy = cfg.get("caddy", {})
    harness_host = cfg_caddy.get("harness_host", "harness.local")
    idp_host = cfg_caddy.get("idp_host", "idp.local")
    metrics_host = cfg_caddy.get("metrics_host", "metrics.local")
    typer.echo(f"\nPlatform ready:")
    typer.echo(f"  harness  http://{harness_host}")
    typer.echo(f"  idp      http://{idp_host}")
    typer.echo(f"  metrics  http://{metrics_host}")


# ---------------------------------------------------------------------------
# harness stop
# ---------------------------------------------------------------------------


@cli.command("stop")
def stop(
    compose_file: Annotated[Optional[Path], typer.Option("--compose-file")] = None,
    project_name: Annotated[Optional[str], typer.Option("--project-name")] = None,
    config: Annotated[Path, typer.Option("--config")] = _HARNESS_YAML,
) -> None:
    """Stop the platform via docker compose down."""
    cfg = _load_cli_config(config)
    run_cfg = cfg.get("run", {})
    compose_file = compose_file or Path(run_cfg.get("compose_file", str(_INFRA_DIR / "docker-compose.yml")))

    if not compose_file.exists():
        typer.echo(f"Error: compose file not found: {compose_file}", err=True)
        raise typer.Exit(2)

    cmd = ["docker", "compose"]
    if project_name:
        cmd += ["-p", project_name]
    cmd += ["-f", str(compose_file), "down"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        typer.echo("Error: docker not found on PATH", err=True)
        raise typer.Exit(3)

    if result.returncode != 0:
        if result.stderr:
            typer.echo(result.stderr.rstrip(), err=True)
        raise typer.Exit(3)

    typer.echo("Platform stopped")
