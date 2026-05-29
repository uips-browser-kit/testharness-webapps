from __future__ import annotations

import os

from src.core.models import AUTH_FAULT_KINDS, FAULT_KINDS, App, PatternType


def build_manifest(
    apps: list[App],
    entity_records: dict[tuple[str, str], list[dict]],
    hosts: list[dict],
    keycloak: dict,
    version: str = "",
    dataset: str = "",
    shared_entities: dict[str, list[str]] | None = None,
    entities: dict | None = None,
) -> dict:
    """Build the harness manifest as a plain dict. Pure function — no I/O."""
    _entities = entities or {}
    return {
        "version": version,
        "dataset": dataset,
        "shared_entities": shared_entities or {},
        "entities": _entities,
        "network": {"hosts": hosts, "hosts_file": "infra/hosts.txt"},
        "apps": [_app_entry(app, entity_records, _entities, apps) for app in apps],
        "users": _build_users(keycloak),
        "idp": _build_idp(keycloak),
        "fault_injection": _build_fault_injection(apps),
        "active_state": {"challenges": "/challenges", "scenarios": "/scenario"},
    }


# ---------------------------------------------------------------------------
# apps
# ---------------------------------------------------------------------------


def _app_entry(
    app: App,
    entity_records: dict[tuple[str, str], list[dict]],
    entities: dict,
    all_apps: list[App],
) -> dict:
    return {
        "id": app.id,
        "vendor": app.vendor,
        "product": app.product,
        "environments": [
            _env_entry(app, env_id, entity_records, entities, all_apps)
            for env_id in app.environments
        ],
    }


def _env_entry(
    app: App,
    env_id: str,
    entity_records: dict[tuple[str, str], list[dict]],
    entities: dict,
    all_apps: list[App],
) -> dict:
    env = app.environments[env_id]
    base_url = f"{env.scheme}://{env.host}"
    if env.base_path and env.base_path != "/":
        base_url += env.base_path.rstrip("/")
    return {
        "id": env_id,
        "base_url": base_url,
        "routes": [
            _route_entry(route, base_url, app.id, entity_records, entities, all_apps)
            for route in app.routes
        ],
        "scenarios": [_scenario_entry(s, app.id, env_id) for s in app.scenarios],
    }


def _route_kind(route) -> str:
    if route.data_entity and (route.data_key_field or route.data_key_param):
        return "detail"
    if route.data_entity:
        return "list"
    return "template-only"


def _lookup_sources(route) -> list[str]:
    has_data = bool(route.data_entity)
    has_template = bool(route.template)
    if has_data and has_template:
        return ["api", "html"]
    if has_data:
        return ["api"]
    if has_template:
        return ["html"]
    return []


def _route_entry(
    route,
    base_url: str,
    app_id: str,
    entity_records: dict[tuple[str, str], list[dict]],
    entities: dict,
    all_apps: list[App],
) -> dict:
    kind = _route_kind(route)
    entry: dict = {
        "id": route.id,
        "kind": kind,
        "supported_methods": route.methods,
    }
    lookup = _lookup_sources(route)

    if kind == "detail":
        url_tpl = _detail_url_template(route, base_url)
        key_param = route.data_key_param or route.data_key_field
        records = entity_records.get((app_id, route.data_entity), [])
        candidates = [str(r[route.data_key_field]) for r in records if route.data_key_field in r]
        entry["url_template"] = url_tpl
        entry["key_param"] = key_param
        entry["entity"] = route.data_entity
        entry["relationships"] = _compute_relationships(route.data_entity, entities, all_apps)
        entry["reverse_relationships"] = _compute_reverse_relationships(route.data_entity, entities, all_apps)
        entry["record_count"] = len(records)
        entry["candidate_count"] = len(candidates)
        entry["candidates"] = candidates
        entry["lookup_sources"] = lookup

    elif kind == "list":
        records = entity_records.get((app_id, route.data_entity), [])
        entry["url"] = _list_url(route, base_url)
        entry["entity"] = route.data_entity
        entry["record_count"] = len(records)
        entry["lookup_sources"] = lookup

    else:  # template-only
        entry["url"] = base_url + route.path
        if lookup:
            entry["lookup_sources"] = lookup

    return entry


def _detail_url_template(route, base_url: str) -> str:
    if route.pattern_type == PatternType.QUERY_ONLY:
        if route.url_template:
            return base_url + route.url_template
        # fallback: all-placeholder
        params = "&".join(f"{p}={{{p}}}" for p in route.query_params)
        return f"{base_url}{route.path}?{params}"
    # PATH (and hash/protocol): base_url + path already has {id} etc.
    return base_url + route.path


def _list_url(route, base_url: str) -> str:
    if route.pattern_type == PatternType.QUERY_ONLY:
        key_params = {route.data_key_param or route.data_key_field}
        fixed = [p for p in route.query_params if p not in key_params]
        params = "&".join(f"{p}={{{p}}}" for p in fixed)
        return f"{base_url}{route.path}?{params}" if params else base_url + route.path
    return base_url + route.path


# ---------------------------------------------------------------------------
# relationship computation (entity-level, Doctrine/Prisma-style)
# ---------------------------------------------------------------------------


def _apps_with_detail_route(entity: str, all_apps: list[App]) -> list[str]:
    found = []
    for app in all_apps:
        for route in app.routes:
            if route.data_entity == entity and route.data_key_field:
                found.append(app.id)
                break
    return found


def _compute_relationships(entity: str, entities: dict, all_apps: list[App]) -> dict:
    result = {}
    for field_name, field_def in entities.get(entity, {}).get("fields", {}).items():
        ref_entity = field_def.get("references", "")
        key_param = field_def.get("key_param", "id")
        navigable_apps = _apps_with_detail_route(ref_entity, all_apps)
        if navigable_apps:
            result[field_name] = {
                "entity": ref_entity,
                "key_param": key_param,
                "apps": navigable_apps,
            }
    return result


def _compute_reverse_relationships(entity: str, entities: dict, all_apps: list[App]) -> dict:
    result = {}
    for other_entity, other_def in entities.items():
        if other_entity == entity:
            continue
        for field_name, field_def in other_def.get("fields", {}).items():
            if field_def.get("references") == entity:
                navigable_apps = _apps_with_detail_route(other_entity, all_apps)
                if navigable_apps:
                    result[other_entity] = {
                        "via_field": field_name,
                        "apps": navigable_apps,
                    }
    return result


# ---------------------------------------------------------------------------
# scenarios
# ---------------------------------------------------------------------------


def _scenario_entry(scenario, app_id: str, env_id: str) -> dict:
    fault = scenario.fault
    effect: dict = {
        "fault_kind": fault.kind if fault else None,
        "http_status": FAULT_KINDS[fault.kind]["http_status"] if fault else None,
        "delay_ms": scenario.delay_ms,
    }
    if fault and fault.kind in AUTH_FAULT_KINDS:
        effect["response_headers"] = {"WWW-Authenticate": 'Bearer realm="harness"'}

    return {
        "name": scenario.name,
        "description": scenario.description,
        "effect": effect,
        "activation": [
            {
                "method": "persistent",
                "description": f"All routes in {app_id}/{env_id} until cleared",
                "set": {"method": "PUT", "url": f"/scenario/{app_id}/{env_id}",
                        "body": {"scenario": scenario.name}},
                "clear": {"method": "DELETE", "url": f"/scenario/{app_id}/{env_id}"},
            },
            {
                "method": "per_request_header",
                "description": "Single request only — no server state written",
                "header": "X-Harness-Scenario",
                "value": scenario.name,
            },
            {
                "method": "route_challenge",
                "description": "Per-route, persistent — overrides active scenario",
                "set": {"method": "POST", "url": f"/challenges/{app_id}/{env_id}/{{route}}",
                        "body": {"fault": {"kind": fault.kind}} if fault else {}},
                "clear": {"method": "DELETE", "url": f"/challenges/{app_id}/{env_id}/{{route}}"},
            },
        ],
    }


# ---------------------------------------------------------------------------
# fault injection
# ---------------------------------------------------------------------------


def _build_fault_injection(apps: list[App]) -> dict:
    return {
        "precedence": [
            "X-Harness-Scenario header (highest — single request)",
            "route challenge via POST /challenges/... (per-route, persistent)",
            "active scenario via PUT /scenario/... (per-app/env, persistent)",
            "normal behaviour (lowest)",
        ],
        "fault_kinds": {k: dict(v) for k, v in FAULT_KINDS.items()},
        "on_request_n": (
            "Set on_request_n in challenge body to fire only on the Nth request then auto-clear"
        ),
        "challenge_api": {
            "set":   {"method": "POST",   "url": "/challenges/{app}/{env}/{route}"},
            "clear": {"method": "DELETE", "url": "/challenges/{app}/{env}/{route}"},
            "list":  {"method": "GET",    "url": "/challenges"},
        },
        "scenario_api": {
            "set":   {"method": "PUT",    "url": "/scenario/{app}/{env}"},
            "clear": {"method": "DELETE", "url": "/scenario/{app}/{env}"},
            "list":  {"method": "GET",    "url": "/scenario"},
        },
    }


# ---------------------------------------------------------------------------
# users / idp
# ---------------------------------------------------------------------------


def _build_users(keycloak: dict) -> list[dict]:
    users = []
    for u in keycloak.get("users", []):
        env_var = u.get("password_env", "")
        env_value = os.environ.get(env_var, "") if env_var else ""
        if env_value:
            password = f"<env:{env_var}>"
            source = "env"
        else:
            password = u["username"]
            source = "default"
        users.append({
            "username": u["username"],
            "email": f"{u['username']}@harness.local",
            "roles": u.get("roles", []),
            "password": password,
            "password_source": source,
        })
    return users


def _build_idp(keycloak: dict) -> dict:
    if not keycloak:
        return {}
    realm = keycloak.get("realm", "harness")
    base = f"http://idp.local/realms/{realm}"
    clients = [
        {"id": c["id"], "flow": c["flow"]}
        for c in keycloak.get("clients", [])
    ]
    return {
        "realm": realm,
        "issuer": base,
        "token_url": f"{base}/protocol/openid-connect/token",
        "auth_url": f"{base}/protocol/openid-connect/auth",
        "clients": clients,
    }


# ---------------------------------------------------------------------------
# hosts.txt parser (used by callers)
# ---------------------------------------------------------------------------


def parse_hosts_file(path) -> list[dict]:
    """Parse infra/hosts.txt into a list of {ip, hostname} dicts, skipping comments."""
    entries = []
    try:
        text = open(path, encoding="utf-8").read()
    except FileNotFoundError:
        return entries
    for line in text.splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            ip = parts[0]
            for hostname in parts[1:]:
                entries.append({"ip": ip, "hostname": hostname})
    return entries
