"""
Tests for src/backend/shaper.py — pure view shaping, no I/O.
"""
import pytest
from pathlib import Path

from src.backend.data_loader import DataLoader
from src.backend.shaper import shape_detail, shape_list
from src.core.config import load_config
from src.core.models import DetailViewData, ListViewData, RouteContext

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


# --- shape_detail ----------------------------------------------------------------


def test_shape_detail_returns_detail_view(salesforce, loader):
    route = salesforce.route("account-detail")
    ctx = RouteContext(app_id="salesforce", route_id="account-detail", env_id="dev", params={"id": "001"})
    raw = loader.get_record("salesforce", "accounts", "id", "001")
    view = shape_detail(salesforce, route, ctx, raw)
    assert isinstance(view, DetailViewData)


def test_shape_detail_entity_title(salesforce, loader):
    route = salesforce.route("account-detail")
    ctx = RouteContext(app_id="salesforce", route_id="account-detail", env_id="dev", params={"id": "001"})
    raw = loader.get_record("salesforce", "accounts", "id", "001")
    view = shape_detail(salesforce, route, ctx, raw)
    assert view.entity_title == "Accounts"


def test_shape_detail_record_present(salesforce, loader):
    route = salesforce.route("account-detail")
    ctx = RouteContext(app_id="salesforce", route_id="account-detail", env_id="dev", params={"id": "001"})
    raw = loader.get_record("salesforce", "accounts", "id", "001")
    view = shape_detail(salesforce, route, ctx, raw)
    assert view.record is not None
    assert view.record["id"] == "001"


def test_shape_detail_record_none_when_not_found(salesforce):
    route = salesforce.route("account-detail")
    ctx = RouteContext(app_id="salesforce", route_id="account-detail", env_id="dev", params={"id": "no-such"})
    view = shape_detail(salesforce, route, ctx, None)
    assert view.record is None


def test_shape_detail_list_url_populated(salesforce, loader):
    """shape_detail computes a back-to-list URL pointing at the sibling list route."""
    route = salesforce.route("account-detail")
    ctx = RouteContext(app_id="salesforce", route_id="account-detail", env_id="dev", params={"id": "001"})
    raw = loader.get_record("salesforce", "accounts", "id", "001")
    view = shape_detail(salesforce, route, ctx, raw)
    assert view.list_url != ""
    assert "salesforce-dev.local" in view.list_url
    assert "Account/list/view" in view.list_url


def test_shape_detail_list_url_query_based(apps, loader):
    """For query-based routes the list URL includes the shared query params."""
    oracle = next(a for a in apps if a.id == "oracle")
    route = oracle.route("invoice-detail")
    ctx = RouteContext(
        app_id="oracle", route_id="invoice-detail", env_id="dev",
        params={"_adf.ctrl-state": "abc123", "invoice_number": "INV001"},
    )
    raw = loader.get_record("oracle", "invoices", "invoice_number", "INV001")
    view = shape_detail(oracle, route, ctx, raw)
    assert view.list_url != ""
    assert "_adf.ctrl-state=abc123" in view.list_url
    assert "invoice_number" not in view.list_url


def test_shape_detail_entity_title_underscores(salesforce, loader):
    """data_entity with underscores becomes title-cased with spaces."""
    route = salesforce.route("opportunity-detail")
    ctx = RouteContext(app_id="salesforce", route_id="opportunity-detail", env_id="dev", params={"id": "001"})
    raw = loader.get_record("salesforce", "opportunities", "id", "001")
    view = shape_detail(salesforce, route, ctx, raw)
    assert view.entity_title == "Opportunities"


# --- shape_list ------------------------------------------------------------------


def test_shape_list_returns_list_view(salesforce, loader):
    route = salesforce.route("account-list")
    ctx = RouteContext(app_id="salesforce", route_id="account-list", env_id="dev", params={})
    raw = loader.get_all("salesforce", "accounts")
    view = shape_list(salesforce, route, ctx, raw)
    assert isinstance(view, ListViewData)


def test_shape_list_entity_title(salesforce, loader):
    route = salesforce.route("account-list")
    ctx = RouteContext(app_id="salesforce", route_id="account-list", env_id="dev", params={})
    raw = loader.get_all("salesforce", "accounts")
    view = shape_list(salesforce, route, ctx, raw)
    assert view.entity_title == "Accounts"


def test_shape_list_records_count(salesforce, loader):
    route = salesforce.route("account-list")
    ctx = RouteContext(app_id="salesforce", route_id="account-list", env_id="dev", params={})
    raw = loader.get_all("salesforce", "accounts")
    view = shape_list(salesforce, route, ctx, raw)
    assert len(view.records) == len(raw)


def test_shape_list_detail_urls_populated(salesforce, loader):
    """shape_list pre-computes one URL per record using the sibling detail route."""
    route = salesforce.route("account-list")
    ctx = RouteContext(app_id="salesforce", route_id="account-list", env_id="dev", params={})
    raw = loader.get_all("salesforce", "accounts")
    view = shape_list(salesforce, route, ctx, raw)
    assert len(view.detail_urls) == len(raw)
    # Each URL should contain the record's id
    for rec in raw:
        assert rec["id"] in view.detail_urls
        assert rec["id"] in view.detail_urls[rec["id"]]


def test_shape_list_detail_key_field(salesforce, loader):
    route = salesforce.route("account-list")
    ctx = RouteContext(app_id="salesforce", route_id="account-list", env_id="dev", params={})
    raw = loader.get_all("salesforce", "accounts")
    view = shape_list(salesforce, route, ctx, raw)
    assert view.detail_key_field == "id"


def test_shape_list_filter_by_path_param(apps, loader):
    """Records are filtered when a URL path param key matches an entity field name."""
    confluence = next(a for a in apps if a.id == "confluence")
    route = confluence.route("space")
    # space_key is both a URL param and a field in the pages entity
    ctx = RouteContext(
        app_id="confluence", route_id="space", env_id="cloud",
        params={"space_key": "ENG"},
    )
    raw = loader.get_all("confluence", "pages")
    view = shape_list(confluence, route, ctx, raw)
    # All returned records must have space_key == "ENG"
    for rec in view.records:
        assert str(rec.get("space_key")) == "ENG"


def test_shape_list_filter_uses_string_coercion(salesforce, loader):
    """Filtering uses str(r.get(k)) == str(v) — numeric IDs still match."""
    route = salesforce.route("account-list")
    raw = loader.get_all("salesforce", "accounts")
    first_id = raw[0]["id"]
    ctx = RouteContext(
        app_id="salesforce", route_id="account-list", env_id="dev",
        params={"id": str(first_id)},
    )
    view = shape_list(salesforce, route, ctx, raw)
    # Only the record with matching id should be present
    assert len(view.records) == 1
    assert view.records[0]["id"] == first_id


def test_shape_list_no_filter_when_param_not_in_entity(salesforce, loader):
    """Params that don't match any entity field don't filter records."""
    route = salesforce.route("account-list")
    ctx = RouteContext(
        app_id="salesforce", route_id="account-list", env_id="dev",
        params={"unrelated_param": "xyz"},
    )
    raw = loader.get_all("salesforce", "accounts")
    view = shape_list(salesforce, route, ctx, raw)
    assert len(view.records) == len(raw)
