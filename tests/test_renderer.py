"""
Tests for src/harness/renderer.py — Jinja2 template rendering.
"""
import pytest
from fastapi.testclient import TestClient

from src.api.app import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _first_candidate(client, app_id: str, env_id: str, route_id: str) -> str:
    """Return the first candidate key value for a detail route from the live manifest."""
    data = client.get("/manifest").json()
    app_entry = next(a for a in data["apps"] if a["id"] == app_id)
    env_entry = next(e for e in app_entry["environments"] if e["id"] == env_id)
    route_entry = next(r for r in env_entry["routes"] if r["id"] == route_id)
    candidates = route_entry.get("candidates", [])
    if not candidates:
        pytest.skip(f"No data for {app_id}/{env_id}/{route_id} in active dataset")
    return candidates[0]


# --- Static file serving ---


def test_base_css_served(client):
    r = client.get("/static/css/base.css")
    assert r.status_code == 200
    assert "text/css" in r.headers["content-type"]


def test_app_css_served(client):
    r = client.get("/static/css/apps/salesforce.css")
    assert r.status_code == 200
    assert "--app-primary" in r.text


# --- Account detail renders HTML ---


def test_account_detail_returns_html(client):
    acct_id = _first_candidate(client, "salesforce", "dev", "account-detail")
    r = client.get(
        f"/lightning/r/Account/{acct_id}/view",
        headers={"host": "salesforce-dev.local"},
    )
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_account_detail_contains_app_name(client):
    acct_id = _first_candidate(client, "salesforce", "dev", "account-detail")
    r = client.get(
        f"/lightning/r/Account/{acct_id}/view",
        headers={"host": "salesforce-dev.local"},
    )
    assert "Lightning" in r.text


def test_account_detail_contains_env_badge(client):
    acct_id = _first_candidate(client, "salesforce", "dev", "account-detail")
    r = client.get(
        f"/lightning/r/Account/{acct_id}/view",
        headers={"host": "salesforce-dev.local"},
    )
    assert "dev" in r.text.lower()


def test_account_detail_loads_app_css(client):
    acct_id = _first_candidate(client, "salesforce", "dev", "account-detail")
    r = client.get(
        f"/lightning/r/Account/{acct_id}/view",
        headers={"host": "salesforce-dev.local"},
    )
    assert "apps/salesforce.css" in r.text


def test_account_detail_nav_active_item(client):
    acct_id = _first_candidate(client, "salesforce", "dev", "account-detail")
    r = client.get(
        f"/lightning/r/Account/{acct_id}/view",
        headers={"host": "salesforce-dev.local"},
    )
    assert 'class="active"' in r.text
    assert 'aria-current="page"' in r.text


def test_account_detail_subnav_expanded(client):
    acct_id = _first_candidate(client, "salesforce", "dev", "account-detail")
    r = client.get(
        f"/lightning/r/Account/{acct_id}/view",
        headers={"host": "salesforce-dev.local"},
    )
    assert 'aria-expanded="true"' in r.text


def test_nonexistent_account_returns_404(client):
    r = client.get(
        "/lightning/r/Account/does-not-exist/view",
        headers={"host": "salesforce-dev.local"},
    )
    assert r.status_code == 404
    assert "text/html" in r.headers["content-type"]


# --- Additional app HTML rendering sanity checks ---


def test_sap_shell_renders_html(client):
    order_number = _first_candidate(client, "sap", "dev", "shell")
    r = client.get(
        f"/sap/bc/ui5_ui5/ui2/ushell?sap-client=100&so={order_number}",
        headers={"host": "sap-dev.local"},
    )
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Fiori" in r.text


def test_jira_issue_renders_html(client):
    issue_key = _first_candidate(client, "jira", "cloud", "issue")
    r = client.get(
        f"/browse/{issue_key}",
        headers={"host": "jira-cloud.local"},
    )
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Jira" in r.text
