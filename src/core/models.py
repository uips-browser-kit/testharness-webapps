from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal


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

    def route(self, route_id: str) -> Route:
        for r in self.routes:
            if r.id == route_id:
                return r
        raise KeyError(f"Route {route_id!r} not found in app {self.id!r}")


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
class Fault:
    kind: str  # "server_error" | "unavailable" | "business_error" | "not_found"
    detail: str = "Simulated fault"


@dataclass
class Challenge:
    delay_ms: int = 0
    fault: Fault | None = None


ChallengeMap = dict[tuple[str, str, str], Challenge]  # (app_id, env_id, route_id)
