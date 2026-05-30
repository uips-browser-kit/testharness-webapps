from __future__ import annotations

from typing import Protocol

from src.backend.data_loader import DataLoader
from src.backend.shaper import shape_detail, shape_list
from src.core.models import (
    App,
    Challenge,
    ChallengeMap,
    RecordNotFound,
    Route,
    RouteContext,
    ScenarioDefinition,
    ScenarioMap,
    ViewData,
)


class ChallengeStore(Protocol):
    def get(self, key: tuple[str, str, str]) -> Challenge | None: ...
    def set(self, key: tuple[str, str, str], challenge: Challenge) -> None: ...
    def clear(self, key: tuple[str, str, str]) -> None: ...
    def all(self) -> ChallengeMap: ...
    def increment_and_get(self, key: tuple[str, str, str]) -> int: ...
    def reset_counter(self, key: tuple[str, str, str]) -> None: ...


class InMemoryChallengeStore:
    """Default in-process challenge store used by the API at runtime."""

    def __init__(self) -> None:
        self._store: ChallengeMap = {}
        self._counters: dict[tuple[str, str, str], int] = {}

    def get(self, key: tuple[str, str, str]) -> Challenge | None:
        return self._store.get(key)

    def set(self, key: tuple[str, str, str], challenge: Challenge) -> None:
        self._store[key] = challenge
        self._counters.pop(key, None)

    def clear(self, key: tuple[str, str, str]) -> None:
        self._store.pop(key, None)
        self._counters.pop(key, None)

    def all(self) -> ChallengeMap:
        return dict(self._store)

    def increment_and_get(self, key: tuple[str, str, str]) -> int:
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]

    def reset_counter(self, key: tuple[str, str, str]) -> None:
        self._counters.pop(key, None)


class ScenarioStore(Protocol):
    def get(self, key: tuple[str, str]) -> str | None: ...
    def set(self, key: tuple[str, str], name: str) -> None: ...
    def clear(self, key: tuple[str, str]) -> None: ...
    def all(self) -> ScenarioMap: ...


class InMemoryScenarioStore:
    def __init__(self) -> None:
        self._store: ScenarioMap = {}

    def get(self, key: tuple[str, str]) -> str | None:
        return self._store.get(key)

    def set(self, key: tuple[str, str], name: str) -> None:
        self._store[key] = name

    def clear(self, key: tuple[str, str]) -> None:
        self._store.pop(key, None)

    def all(self) -> ScenarioMap:
        return dict(self._store)


class HarnessService:
    def __init__(
        self,
        loader: DataLoader,
        challenges: ChallengeStore,
        scenarios: ScenarioStore,
        schema: dict | None = None,
        store: object | None = None,
    ) -> None:
        self._loader = loader
        self._challenges = challenges
        self._scenarios = scenarios
        self._schema = schema
        self._store = store

    def prepare_view(self, app: App, route: Route, ctx: RouteContext) -> ViewData | None:
        """Load and shape view data. Returns None for template-only routes."""
        if not route.data_entity:
            return None
        if route.data_key_field:
            param_name = route.data_key_param or route.data_key_field
            key_value = ctx.params.get(param_name, "")
            raw = self._loader.get_record(ctx.app_id, route.data_entity, route.data_key_field, key_value)
            if raw is None and key_value:
                raise RecordNotFound(route.data_entity, key_value)
            return shape_detail(app, route, ctx, raw, schema=self._schema, store=self._store)
        else:
            raw_list = self._loader.get_all(ctx.app_id, route.data_entity)
            return shape_list(app, route, ctx, raw_list, schema=self._schema)

    def get_challenge(self, key: tuple[str, str, str]) -> Challenge | None:
        ch = self._challenges.get(key)
        if ch is None:
            return None
        if ch.on_request_n is None:
            return ch
        count = self._challenges.increment_and_get(key)
        if count == ch.on_request_n:
            self._challenges.reset_counter(key)
            self._challenges.clear(key)
            return ch
        return None

    def set_challenge(self, key: tuple[str, str, str], challenge: Challenge) -> None:
        self._challenges.set(key, challenge)

    def clear_challenge(self, key: tuple[str, str, str]) -> None:
        self._challenges.clear(key)

    def get_challenges(self) -> ChallengeMap:
        return self._challenges.all()

    def get_active_scenario(self, app: App, app_id: str, env_id: str) -> ScenarioDefinition | None:
        name = self._scenarios.get((app_id, env_id))
        return app.scenario(name) if name else None

    def set_scenario(self, key: tuple[str, str], name: str) -> None:
        self._scenarios.set(key, name)

    def clear_scenario(self, key: tuple[str, str]) -> None:
        self._scenarios.clear(key)

    def get_scenarios(self) -> ScenarioMap:
        return self._scenarios.all()

    def get_all_entity_records(
        self, apps: list[App]
    ) -> dict[tuple[str, str], list[dict]]:
        """Return all entity records keyed by (app_id, entity) for every detail/list route."""
        result: dict[tuple[str, str], list[dict]] = {}
        for app in apps:
            seen: set[str] = set()
            for route in app.routes:
                if route.data_entity and route.data_entity not in seen:
                    seen.add(route.data_entity)
                    result[(app.id, route.data_entity)] = self._loader.get_all(
                        app.id, route.data_entity
                    )
        return result
