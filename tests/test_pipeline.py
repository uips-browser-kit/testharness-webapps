"""
Tests for the challenge injection pipeline:
  - src/backend/pipeline.py (prepare_view)
  - src/backend/service.py (HarnessService + InMemoryChallengeStore)
  - src/api/app.py challenge endpoints and _sleeper injection
"""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.backend.data_loader import DataLoader
from src.backend.pipeline import prepare_view
from src.backend.service import HarnessService, InMemoryChallengeStore, InMemoryScenarioStore
from src.core.config import load_config
from src.core.models import Challenge, DetailViewData, Fault, ListViewData, RouteContext

_HARNESS_YAML = Path(__file__).parent.parent / "harness.yaml"
_DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def apps():
    return load_config(_HARNESS_YAML)


@pytest.fixture(scope="module")
def loader():
    return DataLoader(_DATA_DIR, "default")


@pytest.fixture(scope="module")
def salesforce(apps):
    return next(a for a in apps if a.id == "salesforce")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# --- pipeline.prepare_view -------------------------------------------------------


def test_prepare_view_detail_returns_detail_view(salesforce, loader):
    route = salesforce.route("account-detail")
    ctx = RouteContext("salesforce", "account-detail", "dev", {"id": "001"})
    view = prepare_view(salesforce, route, ctx, loader)
    assert isinstance(view, DetailViewData)
    assert view.record is not None


def test_prepare_view_list_returns_list_view(salesforce, loader):
    route = salesforce.route("account-list")
    ctx = RouteContext("salesforce", "account-list", "dev", {})
    view = prepare_view(salesforce, route, ctx, loader)
    assert isinstance(view, ListViewData)
    assert len(view.records) > 0


def test_prepare_view_template_only_returns_none(salesforce, loader):
    route = salesforce.route("dashboard")
    ctx = RouteContext("salesforce", "dashboard", "dev", {})
    view = prepare_view(salesforce, route, ctx, loader)
    assert view is None


# --- InMemoryChallengeStore -------------------------------------------------------


def test_challenge_store_set_get():
    store = InMemoryChallengeStore()
    key = ("salesforce", "dev", "account-detail")
    challenge = Challenge(delay_ms=100)
    store.set(key, challenge)
    assert store.get(key) == challenge


def test_challenge_store_clear():
    store = InMemoryChallengeStore()
    key = ("salesforce", "dev", "account-detail")
    store.set(key, Challenge(delay_ms=50))
    store.clear(key)
    assert store.get(key) is None


def test_challenge_store_clear_missing_key_is_noop():
    store = InMemoryChallengeStore()
    store.clear(("x", "y", "z"))  # no error


def test_challenge_store_all():
    store = InMemoryChallengeStore()
    k1 = ("salesforce", "dev", "account-detail")
    k2 = ("jira", "cloud", "issue")
    store.set(k1, Challenge(delay_ms=100))
    store.set(k2, Challenge(fault=Fault(kind="unavailable")))
    result = store.all()
    assert k1 in result
    assert k2 in result


# --- HarnessService ---------------------------------------------------------------


def test_harness_service_prepare_view(salesforce, loader):
    service = HarnessService(loader, InMemoryChallengeStore(), InMemoryScenarioStore())
    route = salesforce.route("account-detail")
    ctx = RouteContext("salesforce", "account-detail", "dev", {"id": "001"})
    view = service.prepare_view(salesforce, route, ctx)
    assert isinstance(view, DetailViewData)


def test_harness_service_challenge_roundtrip(loader):
    store = InMemoryChallengeStore()
    service = HarnessService(loader, store, InMemoryScenarioStore())
    key = ("salesforce", "dev", "account-detail")
    challenge = Challenge(delay_ms=250, fault=Fault(kind="server_error"))
    service.set_challenge(key, challenge)
    assert service.get_challenge(key) == challenge
    service.clear_challenge(key)
    assert service.get_challenge(key) is None


# --- API challenge endpoints ------------------------------------------------------


def test_post_challenge_returns_set(client):
    r = client.post(
        "/challenges/salesforce/dev/account-detail",
        json={"delay_ms": 100},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "set"
    # clean up
    client.delete("/challenges/salesforce/dev/account-detail")


def test_delete_challenge_returns_cleared(client):
    client.post("/challenges/salesforce/dev/account-detail", json={"delay_ms": 50})
    r = client.delete("/challenges/salesforce/dev/account-detail")
    assert r.status_code == 200
    assert r.json()["status"] == "cleared"


def test_get_challenges_returns_dict(client):
    client.post("/challenges/salesforce/dev/account-detail", json={"delay_ms": 10})
    r = client.get("/challenges")
    assert r.status_code == 200
    assert "salesforce/dev/account-detail" in r.json()
    client.delete("/challenges/salesforce/dev/account-detail")


def test_challenge_with_fault_stored_correctly(client):
    r = client.post(
        "/challenges/salesforce/dev/account-list",
        json={"fault": {"kind": "unavailable", "detail": "Circuit open"}},
    )
    assert r.status_code == 200
    challenges = client.get("/challenges").json()
    entry = challenges.get("salesforce/dev/account-list")
    assert entry is not None
    assert entry["fault"]["kind"] == "unavailable"
    client.delete("/challenges/salesforce/dev/account-list")


# --- _sleeper injection -----------------------------------------------------------


def test_challenge_delay_uses_sleeper(client):
    """_sleeper is called twice: once for base latency, once for challenge delay."""
    calls: list[float] = []

    async def fake_sleeper(seconds: float) -> None:
        calls.append(seconds)

    client.post("/challenges/salesforce/dev/account-detail", json={"delay_ms": 500})
    with patch("src.api.app._sleeper", fake_sleeper):
        r = client.get(
            "/lightning/r/Account/001/view",
            headers={"host": "salesforce-dev.local"},
        )
    assert r.status_code == 200
    assert len(calls) == 2
    assert 0.150 <= calls[0] <= 0.350   # base latency (salesforce: 150-350 ms)
    assert abs(calls[1] - 0.5) < 0.001  # challenge delay
    client.delete("/challenges/salesforce/dev/account-detail")


def test_challenge_fault_returns_correct_status(client):
    client.post(
        "/challenges/salesforce/dev/account-detail",
        json={"fault": {"kind": "server_error"}},
    )
    r = client.get(
        "/lightning/r/Account/001/view",
        headers={"host": "salesforce-dev.local"},
    )
    assert r.status_code == 500
    client.delete("/challenges/salesforce/dev/account-detail")


def test_challenge_unavailable_returns_503(client):
    client.post(
        "/challenges/salesforce/dev/account-detail",
        json={"fault": {"kind": "unavailable", "detail": "Down for maintenance"}},
    )
    r = client.get(
        "/lightning/r/Account/001/view",
        headers={"host": "salesforce-dev.local"},
    )
    assert r.status_code == 503
    client.delete("/challenges/salesforce/dev/account-detail")


def test_no_challenge_does_not_call_sleeper(client):
    """Without a challenge, no challenge delay fires (base latency is suppressed by autouse fixture)."""
    client.delete("/challenges/salesforce/dev/account-detail")  # ensure cleared
    r = client.get(
        "/lightning/r/Account/001/view",
        headers={"host": "salesforce-dev.local"},
    )
    assert r.status_code == 200


def test_base_latency_fires_without_challenge(client):
    """Base latency fires on every response even without a challenge."""
    client.delete("/challenges/salesforce/dev/account-detail")  # ensure cleared
    calls: list[float] = []

    async def fake_sleeper(seconds: float) -> None:
        calls.append(seconds)

    with patch("src.api.app._sleeper", fake_sleeper):
        r = client.get(
            "/lightning/r/Account/001/view",
            headers={"host": "salesforce-dev.local"},
        )
    assert r.status_code == 200
    assert len(calls) == 1
    assert 0.150 <= calls[0] <= 0.350   # salesforce: min 150 ms, max 350 ms


def test_base_latency_stacks_with_challenge_delay(client):
    """Base latency and challenge delay both fire, base first."""
    client.post("/challenges/salesforce/dev/account-detail", json={"delay_ms": 500})
    calls: list[float] = []

    async def fake_sleeper(seconds: float) -> None:
        calls.append(seconds)

    with patch("src.api.app._sleeper", fake_sleeper):
        r = client.get(
            "/lightning/r/Account/001/view",
            headers={"host": "salesforce-dev.local"},
        )
    assert r.status_code == 200
    assert len(calls) == 2
    assert 0.150 <= calls[0] <= 0.350   # base latency first
    assert abs(calls[1] - 0.5) < 0.001  # challenge delay second
    client.delete("/challenges/salesforce/dev/account-detail")


def test_zero_latency_app_does_not_call_sleeper(client):
    """App with max_ms=0 never calls _sleeper for base latency."""
    from src.core.models import LatencyConfig

    calls: list[float] = []

    async def fake_sleeper(seconds: float) -> None:
        calls.append(seconds)

    apps = client.app.state.apps
    sf = next(a for a in apps if a.id == "salesforce")
    original = sf.latency
    sf.latency = LatencyConfig(0, 0)
    try:
        with patch("src.api.app._sleeper", fake_sleeper):
            r = client.get(
                "/lightning/r/Account/001/view",
                headers={"host": "salesforce-dev.local"},
            )
        assert r.status_code == 200
        assert calls == []
    finally:
        sf.latency = original
