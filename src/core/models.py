from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal


FAULT_KINDS: dict[str, dict] = {
    "server_error":       {"http_status": 500, "retriable": False},
    "unavailable":        {"http_status": 503, "retriable": True},
    "business_error":     {"http_status": 409, "retriable": False},
    "not_found":          {"http_status": 404, "retriable": False},
    "rate_limit":         {"http_status": 429, "retriable": True},
    "auth_error":         {"http_status": 401, "retriable": False},
    "force_logout":       {"http_status": 401, "retriable": False},
    "require_reauth":     {"http_status": 401, "retriable": False},
    "invalidate_session": {"http_status": 401, "retriable": False},
    "forbidden":          {"http_status": 403, "retriable": False},
}

AUTH_FAULT_KINDS: frozenset[str] = frozenset({
    "auth_error", "force_logout", "require_reauth", "invalidate_session"
})


class PatternType(StrEnum):
    PATH = "path"
    QUERY_ONLY = "query"
    HASH = "hash"
    PROTOCOL = "protocol"


class NotServerVisible(Exception):
    pass


@dataclass
class Environment:
    host: str
    base_path: str = "/"
    scheme: str = "http"


@dataclass
class Route:
    id: str
    path: str
    pattern_type: PatternType
    query_params: list[str] = field(default_factory=list)
    server_visible: bool = True
    note: str = ""
    template: str = ""
    data_entity: str = ""
    data_key_field: str = ""
    data_key_param: str = ""
    url_template: str = ""
    methods: list[str] = field(default_factory=lambda: ["GET"])
    relationships: dict[str, dict] = field(default_factory=dict)
    reverse_relationships: dict[str, dict] = field(default_factory=dict)


@dataclass
class NavItem:
    label: str
    route_id: str
    href: str
    children: list[NavItem] = field(default_factory=list)

    @property
    def child_route_ids(self) -> set[str]:
        return {c.route_id for c in self.children}


@dataclass
class App:
    id: str
    vendor: str
    product: str
    environments: dict[str, Environment]
    routes: list[Route]
    nav: list[NavItem] = field(default_factory=list)
    layout: str = "layouts/default.html"
    scenarios: list[ScenarioDefinition] = field(default_factory=list)

    def route(self, route_id: str) -> Route:
        for r in self.routes:
            if r.id == route_id:
                return r
        raise KeyError(f"Route {route_id!r} not found in app {self.id!r}")

    def scenario(self, name: str) -> ScenarioDefinition | None:
        return next((s for s in self.scenarios if s.name == name), None)


@dataclass
class RouteContext:
    app_id: str
    route_id: str
    env_id: str
    params: dict[str, str]


@dataclass
class DetailViewData:
    kind: Literal["detail"] = "detail"
    entity_title: str = ""
    record: dict | None = None
    list_url: str = ""


@dataclass
class ListViewData:
    kind: Literal["list"] = "list"
    entity_title: str = ""
    records: list[dict] = field(default_factory=list)
    detail_urls: dict[str, str] = field(default_factory=dict)
    detail_key_field: str = ""


@dataclass
class TemplateOnlyViewData:
    kind: Literal["template-only"] = "template-only"
    app_id: str = ""
    env_id: str = ""
    route_id: str = ""
    params: dict[str, str] = field(default_factory=dict)


ViewData = DetailViewData | ListViewData | TemplateOnlyViewData


@dataclass
class ErrorViewData:
    kind: Literal["error"] = "error"
    status_code: int = 500
    title: str = ""
    message: str = ""
    retriable: bool = False
    retry_after_s: int | None = None
    request_id: str = ""
    support_code: str = ""


@dataclass
class Fault:
    kind: str  # "server_error" | "unavailable" | "business_error" | "not_found" | "rate_limit" | "auth_error" | "forbidden" | "force_logout" | "require_reauth" | "invalidate_session"
    detail: str = "Simulated fault"
    retriable: bool = False


class RecordNotFound(Exception):
    def __init__(self, entity: str, key_value: str) -> None:
        self.entity = entity
        self.key_value = key_value
        super().__init__(f"{entity} {key_value!r} not found")


@dataclass
class Challenge:
    delay_ms: int = 0
    fault: Fault | None = None
    on_request_n: int | None = None  # fire only on the Nth matching request, then auto-clear


ChallengeMap = dict[tuple[str, str, str], Challenge]  # (app_id, env_id, route_id)


@dataclass
class ScenarioDefinition:
    name: str
    description: str = ""
    delay_ms: int = 0
    fault: Fault | None = None


ScenarioMap = dict[tuple[str, str], str]  # (app_id, env_id) -> active scenario name
