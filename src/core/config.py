from __future__ import annotations

from pathlib import Path

import yaml

from src.core.models import App, Environment, Fault, LatencyConfig, NavItem, PatternType, Route, ScenarioDefinition

_ALLOWED_TOP_LEVEL = {"apps", "data", "keycloak", "prometheus", "caddy", "cli"}


class ConfigError(Exception):
    pass


def load_keycloak_config(path: Path) -> dict:
    """Return the raw keycloak: section from harness.yaml, or {} if absent."""
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {}
    if not isinstance(raw, dict):
        return {}
    return raw.get("keycloak") or {}


def parse_data_set(path: Path) -> str:
    """Return the configured dataset name from harness.yaml, defaulting to 'default'."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    data_raw = raw.get("data") if isinstance(raw, dict) else None
    if isinstance(data_raw, dict):
        return str(data_raw.get("set", "default"))
    return "default"


def parse_shared_entities(path: Path) -> dict[str, list[str]]:
    """Return the shared_entities map from harness.yaml data section.

    Returns entity → list[app_id] declaring which apps share the same primary
    key space for that entity. Empty dict when not declared.
    """
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    data_raw = raw.get("data") if isinstance(raw, dict) else None
    if isinstance(data_raw, dict):
        return dict(data_raw.get("shared_entities", {}))
    return {}


def parse_entities(path: Path) -> dict[str, dict]:
    """Return entity FK definitions from harness.yaml data.entities section."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    data_raw = raw.get("data") if isinstance(raw, dict) else None
    if isinstance(data_raw, dict):
        return dict(data_raw.get("entities", {}))
    return {}


def load_config(path: Path) -> list[App]:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML parse error in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: expected a YAML mapping at top level")

    unknown = set(raw) - _ALLOWED_TOP_LEVEL
    if unknown:
        raise ConfigError(f"{path}: unknown top-level keys: {sorted(unknown)}")

    if "apps" not in raw:
        raise ConfigError(f"{path}: missing required key 'apps'")

    apps_raw = raw["apps"]
    if not isinstance(apps_raw, list) or len(apps_raw) == 0:
        raise ConfigError(f"{path}: 'apps' must be a non-empty list")

    seen_ids: set[str] = set()
    apps: list[App] = []
    for i, app_raw in enumerate(apps_raw):
        app = _parse_app(path, app_raw, i)
        if app.id in seen_ids:
            raise ConfigError(f"{path}: duplicate app id {app.id!r}")
        seen_ids.add(app.id)
        apps.append(app)

    return apps


def _parse_app(path: Path, raw: dict, index: int) -> App:
    _require_fields(
        path, raw, ["id", "vendor", "product", "environments", "routes"], f"apps[{index}]"
    )

    envs_raw = raw["environments"]
    if not isinstance(envs_raw, dict) or len(envs_raw) == 0:
        raise ConfigError(f"{path}: apps[{index}].environments must be a non-empty mapping")

    environments = {
        env_id: Environment(
            host=env["host"],
            base_path=env.get("base_path", "/"),
            scheme=env.get("scheme", "http"),
        )
        for env_id, env in envs_raw.items()
    }

    routes_raw = raw["routes"]
    if not isinstance(routes_raw, list):
        raise ConfigError(f"{path}: apps[{index}].routes must be a list")

    routes = [_parse_route(path, r, index, j) for j, r in enumerate(routes_raw)]

    nav = [_parse_nav_item(item) for item in raw.get("nav", [])]
    scenarios = [_parse_scenario(s) for s in raw.get("scenarios", [])]

    latency = LatencyConfig()
    if lat_raw := raw.get("latency_ms"):
        min_ms = int(lat_raw.get("min", 0))
        max_ms = int(lat_raw.get("max", 0))
        if min_ms > max_ms:
            raise ConfigError(
                f"{path}: apps[{index}].latency_ms min ({min_ms}) > max ({max_ms})"
            )
        latency = LatencyConfig(min_ms=min_ms, max_ms=max_ms)

    return App(
        id=raw["id"],
        vendor=raw["vendor"],
        product=raw["product"],
        environments=environments,
        routes=routes,
        nav=nav,
        layout=raw.get("layout", "layouts/default.html"),
        scenarios=scenarios,
        latency=latency,
    )


def _parse_route(path: Path, raw: dict, app_index: int, route_index: int) -> Route:
    location = f"apps[{app_index}].routes[{route_index}]"
    _require_fields(path, raw, ["id", "path", "pattern_type"], location)
    try:
        pattern_type = PatternType(raw["pattern_type"])
    except ValueError:
        raise ConfigError(
            f"{path}: {location}.pattern_type {raw['pattern_type']!r} is not a valid PatternType"
        ) from None
    return Route(
        id=raw["id"],
        path=raw["path"],
        pattern_type=pattern_type,
        query_params=raw.get("query_params", []),
        server_visible=raw.get("server_visible", True),
        note=raw.get("note", ""),
        template=raw.get("template", ""),
        data_entity=raw.get("data_entity", ""),
        data_key_field=raw.get("data_key_field", ""),
        data_key_param=raw.get("data_key_param", ""),
        url_template=raw.get("url_template", ""),
        methods=raw.get("methods", ["GET"]),
    )


def _parse_scenario(raw: dict) -> ScenarioDefinition:
    if "name" not in raw:
        raise ConfigError("scenario entry missing required field 'name'")
    fault = None
    if fault_data := raw.get("fault"):
        fault = Fault(
            kind=fault_data["kind"],
            detail=fault_data.get("detail", "Simulated fault"),
            retriable=fault_data.get("retriable", False),
        )
    return ScenarioDefinition(
        name=raw["name"],
        description=raw.get("description", ""),
        delay_ms=raw.get("delay_ms", 0),
        fault=fault,
    )


def _parse_nav_item(raw: dict) -> NavItem:
    children = [_parse_nav_item(c) for c in raw.get("children", [])]
    return NavItem(
        label=raw["label"],
        route_id=raw["route_id"],
        href=raw["href"],
        children=children,
    )


def _require_fields(path: Path, raw: dict, fields: list[str], location: str) -> None:
    for f in fields:
        if f not in raw:
            raise ConfigError(f"{path}: {location} missing required field {f!r}")
