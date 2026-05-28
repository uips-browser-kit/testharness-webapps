"""
Tests for Accept-header content negotiation (issue #56).

Acceptance criteria:
- html default (no Accept header, or */* wildcard)
- json requested via Accept: application/json or ?format=json
- ?format= override takes priority over Accept header
- unsupported Accept returns 406
- list, detail, and template-only routes all have typed JSON shapes
"""
import pytest
from fastapi.testclient import TestClient

from src.api.app import app

_SF_DEV = {"host": "salesforce-dev.local"}
_DETAIL = "/lightning/r/Account/001/view"
_LIST = "/lightning/r/Account/list/view"
_HOME = "/lightning/page/home"  # template-only (dashboard route)
_DYNAMICS_DETAIL = "/main.aspx?appid=app-001&pagetype=entityrecord&id=001"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# HTML default
# ---------------------------------------------------------------------------


def test_html_default_no_accept_header(client):
    r = client.get(_DETAIL, headers=_SF_DEV)
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_html_explicit_accept_text_html(client):
    r = client.get(_DETAIL, headers={**_SF_DEV, "accept": "text/html"})
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_wildcard_accept_returns_html(client):
    r = client.get(_DETAIL, headers={**_SF_DEV, "accept": "*/*"})
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_browser_accept_string_returns_html(client):
    browser_accept = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    r = client.get(_DETAIL, headers={**_SF_DEV, "accept": browser_accept})
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


# ---------------------------------------------------------------------------
# JSON via Accept header
# ---------------------------------------------------------------------------


def test_json_explicit_accept_application_json(client):
    r = client.get(_DETAIL, headers={**_SF_DEV, "accept": "application/json"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/json"
    data = r.json()
    assert data["kind"] == "detail"
    assert data["entity_title"] == "Accounts"
    assert data["record"]["id"] == "001"


def test_json_list_route(client):
    r = client.get(_LIST, headers={**_SF_DEV, "accept": "application/json"})
    assert r.status_code == 200
    data = r.json()
    assert data["kind"] == "list"
    assert data["entity_title"] == "Accounts"
    assert len(data["records"]) > 0
    assert "detail_urls" in data


def test_json_template_only_route(client):
    r = client.get(_HOME, headers={**_SF_DEV, "accept": "application/json"})
    assert r.status_code == 200
    data = r.json()
    assert data["kind"] == "template-only"


def test_json_template_only_has_route_context(client):
    r = client.get(_HOME, headers={**_SF_DEV, "accept": "application/json"})
    data = r.json()
    assert data["app_id"] == "salesforce"
    assert data["env_id"] == "dev"
    assert data["route_id"] == "dashboard"
    assert isinstance(data["params"], dict)


def test_json_detail_includes_list_url(client):
    r = client.get(_DETAIL, headers={**_SF_DEV, "accept": "application/json"})
    data = r.json()
    assert "list_url" in data
    assert "salesforce-dev.local" in data["list_url"]


def test_json_query_based_route(client):
    r = client.get(
        _DYNAMICS_DETAIL,
        headers={"host": "dynamics-dev.local", "accept": "application/json"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["kind"] == "detail"


# ---------------------------------------------------------------------------
# ?format= override
# ---------------------------------------------------------------------------


def test_json_format_query_param(client):
    r = client.get(_DETAIL + "?format=json", headers=_SF_DEV)
    assert r.status_code == 200
    data = r.json()
    assert data["kind"] == "detail"


def test_html_format_query_param_overrides_accept(client):
    r = client.get(
        _DETAIL + "?format=html",
        headers={**_SF_DEV, "accept": "application/json"},
    )
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


# ---------------------------------------------------------------------------
# 406 Not Acceptable
# ---------------------------------------------------------------------------


def test_unsupported_accept_returns_406(client):
    r = client.get(_DETAIL, headers={**_SF_DEV, "accept": "text/xml"})
    assert r.status_code == 406


def test_unsupported_accept_multitype_returns_406(client):
    r = client.get(_DETAIL, headers={**_SF_DEV, "accept": "text/xml, image/png"})
    assert r.status_code == 406
