from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PatternType(str, Enum):
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


@dataclass
class Route:
    id: str
    path: str
    pattern_type: PatternType
    query_params: list[str] = field(default_factory=list)
    server_visible: bool = True
    note: str = ""


@dataclass
class App:
    id: str
    vendor: str
    product: str
    environments: dict[str, Environment]
    routes: list[Route]

    def route(self, route_id: str) -> Route:
        for r in self.routes:
            if r.id == route_id:
                return r
        raise KeyError(f"Route {route_id!r} not found in app {self.id!r}")
