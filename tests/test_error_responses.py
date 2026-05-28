"""
ADR-005 contract tests: one case per status code in the stable error contract.
"""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from unittest.mock import patch

from src.harness.app import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# --- 200 -----------------------------------------------------------------------


def test_200_route_matched(client):
    r = client.get(
        "/lightning/r/Account/001/view",
        headers={"host": "sf-dev.local"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["app"] == "salesforce"
    assert body["route"] == "account-detail"


# --- 404 -----------------------------------------------------------------------


def test_404_no_host_match(client):
    r = client.get("/any/path", headers={"host": "no-such-host.local"})
    assert r.status_code == 404


def test_404_no_path_match(client):
    r = client.get("/no/matching/path", headers={"host": "sf-dev.local"})
    assert r.status_code == 404


# --- 422 -----------------------------------------------------------------------


def test_422_not_server_visible():
    from src.core.models import App, Environment, PatternType, Route
    from src.harness.router import ResolveRequest, resolve_url

    hash_app = App(
        id="test-hash",
        vendor="Test",
        product="Test",
        environments={"dev": Environment(host="test.local")},
        routes=[
            Route(
                id="hash-route",
                path="/page#section",
                pattern_type=PatternType.HASH,
                server_visible=False,
            )
        ],
    )
    body = ResolveRequest(
        app="test-hash", environment="dev", route="hash-route", parameters={}
    )
    with pytest.raises(HTTPException) as exc_info:
        resolve_url(body, [hash_app])
    assert exc_info.value.status_code == 422


# --- 500 -----------------------------------------------------------------------


def test_500_unhandled_exception(client):
    with patch("src.harness.app.resolve_route", side_effect=RuntimeError("boom")):
        r = client.get(
            "/lightning/r/Account/001/view",
            headers={"host": "sf-dev.local"},
        )
    assert r.status_code == 500
