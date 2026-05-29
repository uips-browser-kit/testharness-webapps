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
    ViewData,
)


class ChallengeStore(Protocol):
    def get(self, key: tuple[str, str, str]) -> Challenge | None: ...
    def set(self, key: tuple[str, str, str], challenge: Challenge) -> None: ...
    def clear(self, key: tuple[str, str, str]) -> None: ...
    def all(self) -> ChallengeMap: ...


class InMemoryChallengeStore:
    """Default in-process challenge store used by the API at runtime."""

    def __init__(self) -> None:
        self._store: ChallengeMap = {}

    def get(self, key: tuple[str, str, str]) -> Challenge | None:
        return self._store.get(key)

    def set(self, key: tuple[str, str, str], challenge: Challenge) -> None:
        self._store[key] = challenge

    def clear(self, key: tuple[str, str, str]) -> None:
        self._store.pop(key, None)

    def all(self) -> ChallengeMap:
        return dict(self._store)


class HarnessService:
    def __init__(self, loader: DataLoader, challenges: ChallengeStore) -> None:
        self._loader = loader
        self._challenges = challenges

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
            return shape_detail(app, route, ctx, raw)
        else:
            raw_list = self._loader.get_all(ctx.app_id, route.data_entity)
            return shape_list(app, route, ctx, raw_list)

    def get_challenge(self, key: tuple[str, str, str]) -> Challenge | None:
        return self._challenges.get(key)

    def set_challenge(self, key: tuple[str, str, str], challenge: Challenge) -> None:
        self._challenges.set(key, challenge)

    def clear_challenge(self, key: tuple[str, str, str]) -> None:
        self._challenges.clear(key)

    def get_challenges(self) -> ChallengeMap:
        return self._challenges.all()
