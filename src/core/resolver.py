from __future__ import annotations

import re
from urllib.parse import urlencode

from src.core.models import App, NotServerVisible, PatternType


def resolve(app: App, route_id: str, env_id: str, params: dict[str, str]) -> str:
    env = app.environments[env_id]
    route = app.route(route_id)

    if not route.server_visible:
        raise NotServerVisible(
            f"{app.id}.{route_id} uses {route.pattern_type.value} routing — not visible to the server"
        )

    base = env.base_path.rstrip("/")
    path = route.path
    query: dict[str, str] = {}

    if route.pattern_type == PatternType.PATH:
        for name in re.findall(r"\{(\w+)\}", path):
            if name in params:
                path = path.replace(f"{{{name}}}", params[name])
        for qp in route.query_params:
            if qp in params:
                query[qp] = params[qp]

    elif route.pattern_type == PatternType.QUERY_ONLY:
        for qp in route.query_params:
            if qp in params:
                query[qp] = params[qp]

    url = f"http://{env.host}{base}{path}"
    if query:
        url += "?" + urlencode(query)
    return url
