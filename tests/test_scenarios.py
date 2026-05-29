"""
Tests for named scenario model: persistent activation + per-request header.
Covers GitHub issues #89–#95 (epic #88).
"""
import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from src.api.app import app
from src.core.config import load_config

_SF_DEV = {"host": "salesforce-dev.local"}
_SF_DETAIL = "/lightning/r/Account/001/view"
_SF_LIST = "/lightning/r/Account/list/view"
_SF_CONTACT_LIST = "/lightning/r/Contact/list/view"


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
        c.delete("/scenario/salesforce/dev")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def test_salesforce_scenarios_loaded_from_config():
    apps = load_config(Path("harness.yaml"))
    sf = next(a for a in apps if a.id == "salesforce")
    assert len(sf.scenarios) == 4
    names = {s.name for s in sf.scenarios}
    assert names == {"session-expired", "rate-limited", "degraded", "record-locked"}


def test_scenario_lookup_returns_correct_definition():
    apps = load_config(Path("harness.yaml"))
    sf = next(a for a in apps if a.id == "salesforce")
    s = sf.scenario("session-expired")
    assert s is not None
    assert s.fault is not None
    assert s.fault.kind == "auth_error"


def test_scenario_lookup_returns_none_for_unknown():
    apps = load_config(Path("harness.yaml"))
    sf = next(a for a in apps if a.id == "salesforce")
    assert sf.scenario("nonexistent") is None


# ---------------------------------------------------------------------------
# Scenario API endpoints
# ---------------------------------------------------------------------------


def test_set_scenario_returns_set_status(client):
    r = client.put("/scenario/salesforce/dev", json={"scenario": "rate-limited"})
    assert r.status_code == 200
    assert r.json()["status"] == "set"
    assert r.json()["scenario"] == "rate-limited"


def test_get_scenario_returns_active_name(client):
    client.put("/scenario/salesforce/dev", json={"scenario": "record-locked"})
    r = client.get("/scenario/salesforce/dev")
    assert r.status_code == 200
    assert r.json()["scenario"] == "record-locked"


def test_clear_scenario_removes_active(client):
    client.put("/scenario/salesforce/dev", json={"scenario": "rate-limited"})
    client.delete("/scenario/salesforce/dev")
    r = client.get("/scenario/salesforce/dev")
    assert r.json()["scenario"] is None


def test_list_scenarios_shows_active(client):
    client.put("/scenario/salesforce/dev", json={"scenario": "session-expired"})
    r = client.get("/scenario")
    assert r.status_code == 200
    assert r.json().get("salesforce/dev") == "session-expired"


def test_set_unknown_scenario_returns_404(client):
    r = client.put("/scenario/salesforce/dev", json={"scenario": "nonexistent"})
    assert r.status_code == 404


def test_set_scenario_missing_field_returns_422(client):
    r = client.put("/scenario/salesforce/dev", json={})
    assert r.status_code == 422


def test_set_scenario_unknown_app_returns_404(client):
    r = client.put("/scenario/no-such-app/dev", json={"scenario": "session-expired"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Persistent scenario — applies to all routes
# ---------------------------------------------------------------------------


def test_persistent_scenario_applies_to_detail_route(client):
    client.put("/scenario/salesforce/dev", json={"scenario": "session-expired"})
    r = client.get(_SF_DETAIL, headers={**_SF_DEV, "accept": "application/json"})
    assert r.status_code == 401


def test_persistent_scenario_applies_to_list_route(client):
    client.put("/scenario/salesforce/dev", json={"scenario": "session-expired"})
    r = client.get(_SF_LIST, headers={**_SF_DEV, "accept": "application/json"})
    assert r.status_code == 401


def test_persistent_scenario_applies_to_multiple_routes(client):
    client.put("/scenario/salesforce/dev", json={"scenario": "rate-limited"})
    r1 = client.get(_SF_DETAIL, headers={**_SF_DEV, "accept": "application/json"})
    r2 = client.get(_SF_LIST, headers={**_SF_DEV, "accept": "application/json"})
    r3 = client.get(_SF_CONTACT_LIST, headers={**_SF_DEV, "accept": "application/json"})
    assert r1.status_code == 429
    assert r2.status_code == 429
    assert r3.status_code == 429


def test_persistent_scenario_clear_restores_200(client):
    client.put("/scenario/salesforce/dev", json={"scenario": "session-expired"})
    client.delete("/scenario/salesforce/dev")
    r = client.get(_SF_DETAIL, headers={**_SF_DEV, "accept": "application/json"})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Per-request header — applies to that request only
# ---------------------------------------------------------------------------


def test_header_scenario_applies_to_single_request(client):
    r = client.get(_SF_DETAIL, headers={
        **_SF_DEV,
        "accept": "application/json",
        "x-harness-scenario": "session-expired",
    })
    assert r.status_code == 401


def test_header_scenario_does_not_affect_subsequent_request(client):
    client.get(_SF_DETAIL, headers={
        **_SF_DEV,
        "accept": "application/json",
        "x-harness-scenario": "session-expired",
    })
    r = client.get(_SF_DETAIL, headers={**_SF_DEV, "accept": "application/json"})
    assert r.status_code == 200


def test_header_scenario_rate_limited_returns_429(client):
    r = client.get(_SF_DETAIL, headers={
        **_SF_DEV,
        "accept": "application/json",
        "x-harness-scenario": "rate-limited",
    })
    assert r.status_code == 429


# ---------------------------------------------------------------------------
# Precedence
# ---------------------------------------------------------------------------


def test_route_challenge_overrides_persistent_scenario(client):
    client.put("/scenario/salesforce/dev", json={"scenario": "rate-limited"})
    client.post("/challenges/salesforce/dev/account-detail", json={"fault": {"kind": "server_error"}})
    r = client.get(_SF_DETAIL, headers={**_SF_DEV, "accept": "application/json"})
    client.delete("/challenges/salesforce/dev/account-detail")
    assert r.status_code == 500  # challenge wins over scenario (rate_limit → 429)


def test_route_challenge_overrides_header_scenario(client):
    client.post("/challenges/salesforce/dev/account-detail", json={"fault": {"kind": "server_error"}})
    r = client.get(_SF_DETAIL, headers={
        **_SF_DEV,
        "accept": "application/json",
        "x-harness-scenario": "session-expired",
    })
    client.delete("/challenges/salesforce/dev/account-detail")
    assert r.status_code == 500  # challenge wins over header


def test_header_overrides_persistent_scenario(client):
    client.put("/scenario/salesforce/dev", json={"scenario": "rate-limited"})
    r = client.get(_SF_DETAIL, headers={
        **_SF_DEV,
        "accept": "application/json",
        "x-harness-scenario": "session-expired",
    })
    assert r.status_code == 401  # header (auth_error→401) wins over persistent (rate_limit→429)


def test_persistent_still_active_after_header_request(client):
    client.put("/scenario/salesforce/dev", json={"scenario": "rate-limited"})
    client.get(_SF_DETAIL, headers={
        **_SF_DEV,
        "accept": "application/json",
        "x-harness-scenario": "session-expired",
    })
    r = client.get(_SF_DETAIL, headers={**_SF_DEV, "accept": "application/json"})
    assert r.status_code == 429  # persistent still active


# ---------------------------------------------------------------------------
# Unknown header scenario — ignored, no error
# ---------------------------------------------------------------------------


def test_unknown_header_scenario_ignored(client):
    r = client.get(_SF_DETAIL, headers={
        **_SF_DEV,
        "accept": "application/json",
        "x-harness-scenario": "no-such-scenario",
    })
    assert r.status_code == 200
