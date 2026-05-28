"""
Tests for src/harness/renderer.py — Jinja2 template rendering.
"""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.harness.app import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


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
    r = client.get(
        "/lightning/r/Account/001/view",
        headers={"host": "sf-dev.local"},
    )
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_account_detail_contains_record_name(client):
    r = client.get(
        "/lightning/r/Account/001/view",
        headers={"host": "sf-dev.local"},
    )
    assert "Rodriguez" in r.text


def test_account_detail_contains_app_name(client):
    r = client.get(
        "/lightning/r/Account/001/view",
        headers={"host": "sf-dev.local"},
    )
    assert "Lightning" in r.text


def test_account_detail_contains_env_badge(client):
    r = client.get(
        "/lightning/r/Account/001/view",
        headers={"host": "sf-dev.local"},
    )
    assert "dev" in r.text.lower()


def test_account_detail_loads_app_css(client):
    r = client.get(
        "/lightning/r/Account/001/view",
        headers={"host": "sf-dev.local"},
    )
    assert "apps/salesforce.css" in r.text


def test_account_detail_nav_active_item(client):
    r = client.get(
        "/lightning/r/Account/001/view",
        headers={"host": "sf-dev.local"},
    )
    assert 'class="active"' in r.text
    assert 'aria-current="page"' in r.text


def test_account_detail_subnav_expanded(client):
    r = client.get(
        "/lightning/r/Account/001/view",
        headers={"host": "sf-dev.local"},
    )
    assert 'aria-expanded="true"' in r.text


def test_nonexistent_account_still_renders(client):
    r = client.get(
        "/lightning/r/Account/does-not-exist/view",
        headers={"host": "sf-dev.local"},
    )
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


# --- Routes without a template return JSON ---


def test_no_template_returns_json(client):
    r = client.get(
        "/lightning/page/home",
        headers={"host": "sf-dev.local"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["route"] == "dashboard"
