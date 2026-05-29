"""
ADR-005 contract tests: one case per status code in the stable error contract.
"""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from unittest.mock import patch

from src.api.app import app

_SF_DEV = {"host": "salesforce-dev.local"}
_SF_PROD = {"host": "salesforce-prod.local"}
_SF_DETAIL = "/lightning/r/Account/001/view"
_SF_OPP_DETAIL = "/lightning/r/Opportunity/opp001/view"


@pytest.fixture(scope="module")
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# --- 200 -----------------------------------------------------------------------


def test_200_route_matched(client):
    r = client.get(_SF_DETAIL, headers=_SF_DEV)
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "salesforce" in r.text.lower()


# --- 404 -----------------------------------------------------------------------


def test_unknown_host_returns_harness_index(client):
    r = client.get("/any/path", headers={"host": "no-such-host.local"})
    assert r.status_code == 200
    assert "testharness-webapps" in r.text


def test_404_no_path_match_returns_html(client):
    r = client.get("/no/matching/path", headers=_SF_DEV)
    assert r.status_code == 404
    assert "text/html" in r.headers["content-type"]


def test_404_no_path_match_json_accept(client):
    r = client.get("/no/matching/path", headers={**_SF_DEV, "accept": "application/json"})
    assert r.status_code == 404
    data = r.json()
    assert data["kind"] == "error"
    assert data["status_code"] == 404
    assert not data["retriable"]


# --- 406 -----------------------------------------------------------------------


def test_406_unsupported_accept_returns_html_error(client):
    r = client.get(_SF_DETAIL, headers={**_SF_DEV, "accept": "text/xml"})
    assert r.status_code == 406
    assert "text/html" in r.headers["content-type"]
    assert "406" in r.text


# --- 422 -----------------------------------------------------------------------


def test_422_not_server_visible():
    from src.core.models import App, Environment, PatternType, Route
    from src.api.router import ResolveRequest, resolve_url

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
    with patch("src.api.app.resolve_route", side_effect=RuntimeError("boom")):
        r = client.get(_SF_DETAIL, headers=_SF_DEV)
    assert r.status_code == 500


# --- Error template HTML shape -------------------------------------------------


def test_html_error_has_status_code_in_body(client):
    r = client.get("/no/matching/path", headers=_SF_DEV)
    assert r.status_code == 404
    assert "404" in r.text


def test_html_error_has_request_id(client):
    r = client.get("/no/matching/path", headers=_SF_DEV)
    assert "Request ID:" in r.text


def test_html_error_request_id_passthrough(client):
    r = client.get("/no/matching/path", headers={**_SF_DEV, "x-request-id": "test-req-abc"})
    assert "test-req-abc" in r.text


def test_html_error_generated_request_id_when_absent(client):
    r = client.get("/no/matching/path", headers=_SF_DEV)
    # UUID4 format: 8-4-4-4-12 hex chars
    import re
    assert re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", r.text)


# --- JSON error payload shape --------------------------------------------------


def test_json_error_payload_shape(client):
    r = client.get(_SF_DETAIL, headers={**_SF_DEV, "accept": "application/json", "x-request-id": "req-123"})
    # Inject a 503 via challenge to get a JSON error response
    client.post("/challenges/salesforce/dev/account-detail", json={"delay_ms": 0, "fault": {"kind": "unavailable"}})
    r = client.get(_SF_DETAIL, headers={**_SF_DEV, "accept": "application/json"})
    client.delete("/challenges/salesforce/dev/account-detail")
    assert r.status_code == 503
    data = r.json()
    assert data["kind"] == "error"
    assert data["status_code"] == 503
    assert data["retriable"] is True
    assert data["request_id"]


def test_json_error_retriable_true_for_503(client):
    client.post("/challenges/salesforce/dev/account-detail", json={"fault": {"kind": "unavailable"}})
    r = client.get(_SF_DETAIL, headers={**_SF_DEV, "accept": "application/json"})
    client.delete("/challenges/salesforce/dev/account-detail")
    assert r.status_code == 503
    assert r.json()["retriable"] is True


def test_json_error_retriable_false_for_409(client):
    client.post("/challenges/salesforce/dev/account-detail", json={"fault": {"kind": "business_error"}})
    r = client.get(_SF_DETAIL, headers={**_SF_DEV, "accept": "application/json"})
    client.delete("/challenges/salesforce/dev/account-detail")
    assert r.status_code == 409
    assert r.json()["retriable"] is False


def test_json_error_request_id_passthrough(client):
    client.post("/challenges/salesforce/dev/account-detail", json={"fault": {"kind": "unavailable"}})
    r = client.get(_SF_DETAIL, headers={**_SF_DEV, "accept": "application/json", "x-request-id": "corr-xyz"})
    client.delete("/challenges/salesforce/dev/account-detail")
    assert r.json()["request_id"] == "corr-xyz"


# --- rate_limit (429) ----------------------------------------------------------


def test_rate_limit_fault_returns_429(client):
    client.post("/challenges/salesforce/dev/account-detail", json={"fault": {"kind": "rate_limit"}})
    r = client.get(_SF_DETAIL, headers={**_SF_DEV, "accept": "application/json"})
    client.delete("/challenges/salesforce/dev/account-detail")
    assert r.status_code == 429
    assert r.json()["retriable"] is True


# --- retriable field on Fault --------------------------------------------------


def test_fault_retriable_field_stored_and_returned(client):
    client.post(
        "/challenges/salesforce/dev/account-list",
        json={"fault": {"kind": "unavailable", "retriable": True}},
    )
    challenges = client.get("/challenges").json()
    entry = challenges.get("salesforce/dev/account-list")
    assert entry is not None
    assert entry["fault"]["retriable"] is True
    client.delete("/challenges/salesforce/dev/account-list")


# --- #76: 401 / 403 fault kinds ------------------------------------------------


def test_auth_error_fault_returns_401(client):
    client.post("/challenges/salesforce/dev/account-detail",
                json={"fault": {"kind": "auth_error"}})
    r = client.get(_SF_DETAIL, headers={**_SF_DEV, "accept": "application/json"})
    client.delete("/challenges/salesforce/dev/account-detail")
    assert r.status_code == 401
    assert r.json()["retriable"] is False


def test_forbidden_fault_returns_403(client):
    client.post("/challenges/salesforce/dev/account-detail",
                json={"fault": {"kind": "forbidden"}})
    r = client.get(_SF_DETAIL, headers={**_SF_DEV, "accept": "application/json"})
    client.delete("/challenges/salesforce/dev/account-detail")
    assert r.status_code == 403
    assert r.json()["retriable"] is False


# --- #73: 404 on missing records -----------------------------------------------


def test_missing_record_returns_404_html(client):
    r = client.get("/lightning/r/Opportunity/UNKNOWN/view",
                   headers={**_SF_PROD, "accept": "text/html"})
    assert r.status_code == 404
    assert "Not Found" in r.text


def test_missing_record_returns_404_json(client):
    r = client.get("/lightning/r/Opportunity/UNKNOWN/view",
                   headers={**_SF_PROD, "accept": "application/json"})
    assert r.status_code == 404
    assert r.json()["status_code"] == 404


def test_existing_record_still_200(client):
    r = client.get(_SF_OPP_DETAIL, headers={**_SF_PROD, "accept": "text/html"})
    assert r.status_code == 200


# --- #74: support_code ---------------------------------------------------------


def test_support_code_populated_on_known_route(client):
    client.post("/challenges/salesforce/dev/account-detail",
                json={"fault": {"kind": "server_error"}})
    r = client.get(_SF_DETAIL, headers={**_SF_DEV, "accept": "application/json"})
    client.delete("/challenges/salesforce/dev/account-detail")
    data = r.json()
    assert data["support_code"].startswith("salesforce/dev/account-detail:")
    assert "500" in data["support_code"]


def test_support_code_empty_on_unmatched_route(client):
    r = client.get("/no/such/path",
                   headers={"host": "salesforce-dev.local", "accept": "application/json"})
    data = r.json()
    assert data["support_code"] == ""


# --- #75: per-app branded error template ---------------------------------------


def test_salesforce_error_uses_branded_template(client):
    client.post("/challenges/salesforce/dev/account-detail",
                json={"fault": {"kind": "server_error"}})
    r = client.get(_SF_DETAIL, headers={**_SF_DEV, "accept": "text/html"})
    client.delete("/challenges/salesforce/dev/account-detail")
    assert r.status_code == 500
    assert "Salesforce Sans" in r.text


def test_non_salesforce_error_uses_shared_template(client):
    r = client.get("/no/such/path",
                   headers={"host": "salesforce-dev.local", "accept": "text/html"})
    assert "Request ID:" in r.text
