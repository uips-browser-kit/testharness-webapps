"""
Tests for on_request_n tripwire mode: fires on Nth request, then auto-clears.
Covers GitHub issues #83-#86 (epic #82).
"""
import pytest
from fastapi.testclient import TestClient

from src.api.app import app

_SF_DEV = {"host": "salesforce-dev.local"}
_SF_DETAIL = "/lightning/r/Account/001/view"
_SF_LIST = "/lightning/r/Account/list/view"


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
        c.delete("/challenges/salesforce/dev/account-detail")
        c.delete("/challenges/salesforce/dev/account-list")


def _set(client, route: str, **body):
    return client.post(f"/challenges/salesforce/dev/{route}", json=body)


def _get_detail(client, **extra_headers):
    return client.get(_SF_DETAIL, headers={**_SF_DEV, "accept": "application/json", **extra_headers})


# ---------------------------------------------------------------------------
# on_request_n fires on Nth request and auto-clears
# ---------------------------------------------------------------------------


def test_on_request_n_fires_on_nth(client):
    _set(client, "account-detail", fault={"kind": "server_error"}, on_request_n=3)
    assert _get_detail(client).status_code == 200  # 1
    assert _get_detail(client).status_code == 200  # 2
    assert _get_detail(client).status_code == 500  # 3 — fires
    assert _get_detail(client).status_code == 200  # 4 — auto-cleared


def test_on_request_n_1_fires_immediately_and_clears(client):
    _set(client, "account-detail", fault={"kind": "server_error"}, on_request_n=1)
    assert _get_detail(client).status_code == 500  # 1 — fires
    assert _get_detail(client).status_code == 200  # 2 — auto-cleared


def test_on_request_n_2_fires_on_second_request(client):
    _set(client, "account-detail", fault={"kind": "unavailable"}, on_request_n=2)
    assert _get_detail(client).status_code == 200   # 1
    assert _get_detail(client).status_code == 503   # 2 — fires
    assert _get_detail(client).status_code == 200   # 3 — auto-cleared


# ---------------------------------------------------------------------------
# Auth fault kinds all produce 401 + WWW-Authenticate header
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["force_logout", "require_reauth", "invalidate_session", "auth_error"])
def test_auth_fault_kinds_return_401(client, kind):
    _set(client, "account-detail", fault={"kind": kind})
    r = _get_detail(client)
    assert r.status_code == 401
    client.delete("/challenges/salesforce/dev/account-detail")


@pytest.mark.parametrize("kind", ["force_logout", "require_reauth", "invalidate_session", "auth_error"])
def test_auth_fault_kinds_include_www_authenticate(client, kind):
    _set(client, "account-detail", fault={"kind": kind})
    r = _get_detail(client)
    assert r.status_code == 401
    assert "WWW-Authenticate" in r.headers
    assert r.headers["WWW-Authenticate"] == 'Bearer realm="harness"'
    client.delete("/challenges/salesforce/dev/account-detail")


def test_non_auth_fault_no_www_authenticate(client):
    _set(client, "account-detail", fault={"kind": "server_error"})
    r = _get_detail(client)
    assert r.status_code == 500
    assert "WWW-Authenticate" not in r.headers


# ---------------------------------------------------------------------------
# on_request_n validation
# ---------------------------------------------------------------------------


def test_set_on_request_n_zero_returns_422(client):
    r = _set(client, "account-detail", fault={"kind": "server_error"}, on_request_n=0)
    assert r.status_code == 422


def test_set_on_request_n_negative_returns_422(client):
    r = _set(client, "account-detail", fault={"kind": "server_error"}, on_request_n=-1)
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# list_challenges shows on_request_n field
# ---------------------------------------------------------------------------


def test_list_challenges_includes_on_request_n(client):
    _set(client, "account-detail", fault={"kind": "server_error"}, on_request_n=5)
    data = client.get("/challenges").json()
    assert "salesforce/dev/account-detail" in data
    assert data["salesforce/dev/account-detail"]["on_request_n"] == 5


def test_list_challenges_on_request_n_null_when_not_set(client):
    _set(client, "account-detail", fault={"kind": "server_error"})
    data = client.get("/challenges").json()
    assert data["salesforce/dev/account-detail"]["on_request_n"] is None


# ---------------------------------------------------------------------------
# Concurrent challenges have independent counters
# ---------------------------------------------------------------------------


def test_concurrent_challenges_have_independent_counters(client):
    _set(client, "account-detail", fault={"kind": "server_error"}, on_request_n=2)
    _set(client, "account-list", fault={"kind": "unavailable"}, on_request_n=2)

    assert _get_detail(client).status_code == 200   # detail: 1
    r_list = client.get(_SF_LIST, headers={**_SF_DEV, "accept": "application/json"})
    assert r_list.status_code == 200                # list: 1

    assert _get_detail(client).status_code == 500   # detail: 2 — fires
    r_list2 = client.get(_SF_LIST, headers={**_SF_DEV, "accept": "application/json"})
    assert r_list2.status_code == 503               # list: 2 — fires independently

    client.delete("/challenges/salesforce/dev/account-list")


# ---------------------------------------------------------------------------
# Setting a challenge resets its counter
# ---------------------------------------------------------------------------


def test_reset_on_set_clears_counter(client):
    _set(client, "account-detail", fault={"kind": "server_error"}, on_request_n=2)
    assert _get_detail(client).status_code == 200   # count=1
    # Re-set the challenge — counter should reset
    _set(client, "account-detail", fault={"kind": "server_error"}, on_request_n=2)
    assert _get_detail(client).status_code == 200   # count=1 again (reset)
    assert _get_detail(client).status_code == 500   # count=2 — fires
