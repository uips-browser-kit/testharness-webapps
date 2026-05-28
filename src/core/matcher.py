from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote

from src.core.models import App, PatternType


@dataclass
class MatchResult:
    app_id: str
    route_id: str
    env_id: str
    params: dict[str, str]


def match(host: str, path: str, query: dict[str, str], apps: list[App]) -> MatchResult | None:
    path = unquote(path)
    for app in apps:
        for env_id, env in app.environments.items():
            if env.host != host:
                continue
            base = env.base_path.rstrip("/")
            if base:
                if not path.startswith(base):
                    continue
                rel_path = path[len(base) :]
            else:
                rel_path = path
            for route in app.routes:
                if not route.server_visible:
                    continue
                result = _try_match(app.id, route, env_id, rel_path, query)
                if result is not None:
                    return result
    return None


def _try_match(
    app_id: str, route, env_id: str, path: str, query: dict[str, str]
) -> MatchResult | None:
    if route.pattern_type == PatternType.PATH:
        pattern, names = _path_to_regex(route.path)
        m = pattern.match(path)
        if m is None:
            return None
        params = dict(zip(names, m.groups()))
        for qp in route.query_params:
            if qp in query:
                params[qp] = query[qp]
        return MatchResult(app_id=app_id, route_id=route.id, env_id=env_id, params=params)

    if route.pattern_type == PatternType.QUERY_ONLY:
        if path != route.path:
            return None
        if not all(qp in query for qp in route.query_params):
            return None
        return MatchResult(
            app_id=app_id,
            route_id=route.id,
            env_id=env_id,
            params={qp: query[qp] for qp in route.query_params},
        )

    return None


def _path_to_regex(path: str) -> tuple[re.Pattern, list[str]]:
    names: list[str] = []
    parts = re.split(r"\{(\w+)\}", path)
    pattern = ""
    for i, part in enumerate(parts):
        if i % 2 == 0:
            pattern += re.escape(unquote(part))
        else:
            names.append(part)
            pattern += "([^/]+)"
    return re.compile("^" + pattern + "$"), names
