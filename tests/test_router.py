import pytest
from fastapi.testclient import TestClient

from src.harness.app import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# --- health -------------------------------------------------------------------


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# --- catch-all routing --------------------------------------------------------


def test_path_route_returns_match(client):
    r = client.get(
        "/lightning/r/Account/001/view",
        headers={"host": "salesforce-dev.local"},
    )
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Lightning" in r.text


def test_query_route_returns_match(client):
    r = client.get(
        "/main.aspx?appid=app-001&pagetype=entityrecord&id=001",
        headers={"host": "dynamics-dev.local"},
    )
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Dynamics" in r.text


def test_unknown_host_returns_404(client):
    r = client.get("/some/path", headers={"host": "unknown.host.local"})
    assert r.status_code == 404


def test_unknown_path_returns_404(client):
    r = client.get("/does/not/exist", headers={"host": "salesforce-dev.local"})
    assert r.status_code == 404


# --- POST /match --------------------------------------------------------------


def test_post_match_known_route(client):
    r = client.post(
        "/match",
        json={
            "host": "salesforce-dev.local",
            "path": "/lightning/r/Account/001/view",
            "method": "GET",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["app"] == "salesforce"
    assert body["environment"] == "dev"
    assert body["route"] == "account-detail"
    assert body["parameters"]["id"] == "001"


def test_post_match_no_match_returns_404(client):
    r = client.post(
        "/match",
        json={"host": "salesforce-dev.local", "path": "/nonexistent"},
    )
    assert r.status_code == 404


def test_post_match_jira(client):
    r = client.post(
        "/match",
        json={
            "host": "jira-cloud.local",
            "path": "/browse/ABC-123",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["app"] == "jira"
    assert body["environment"] == "cloud"
    assert body["parameters"]["issue_key"] == "ABC-123"


# --- POST /resolve ------------------------------------------------------------


def test_post_resolve_path_route(client):
    r = client.post(
        "/resolve",
        json={
            "app": "salesforce",
            "environment": "dev",
            "route": "account-detail",
            "parameters": {"id": "001"},
        },
    )
    assert r.status_code == 200
    assert r.json()["url"] == "http://salesforce-dev.local/lightning/r/Account/001/view"


def test_post_resolve_query_route(client):
    r = client.post(
        "/resolve",
        json={
            "app": "dynamics",
            "environment": "dev",
            "route": "record",
            "parameters": {"appid": "app-001", "pagetype": "entityrecord", "id": "001"},
        },
    )
    assert r.status_code == 200
    assert "main.aspx" in r.json()["url"]


def test_post_resolve_unknown_app_returns_404(client):
    r = client.post(
        "/resolve",
        json={
            "app": "no-such-app",
            "environment": "dev",
            "route": "some-route",
            "parameters": {},
        },
    )
    assert r.status_code == 404


def test_post_resolve_unknown_route_returns_404(client):
    r = client.post(
        "/resolve",
        json={
            "app": "salesforce",
            "environment": "dev",
            "route": "no-such-route",
            "parameters": {},
        },
    )
    assert r.status_code == 404


def test_post_resolve_unknown_environment_returns_404(client):
    r = client.post(
        "/resolve",
        json={
            "app": "salesforce",
            "environment": "staging",
            "route": "account-detail",
            "parameters": {"id": "001"},
        },
    )
    assert r.status_code == 404
