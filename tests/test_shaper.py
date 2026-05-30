"""
Tests for src/backend/shaper.py — pure view shaping, no I/O.
"""
import dataclasses
import pytest
from pathlib import Path

from src.backend.canonical_store import CanonicalStore
from src.backend.data_loader import DataLoader
from src.backend.shaper import shape_detail, shape_list
from src.core.config import load_config
from src.core.models import DetailViewData, ListViewData, RelatedConfig, RouteContext
from src.core.schema import load_schema

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


# --- list_fields projection -------------------------------------------------------


def test_shape_list_projects_to_list_fields(salesforce, loader):
    """When list_fields is set, records contain only those keys."""
    route = dataclasses.replace(salesforce.route("account-list"), list_fields=["name", "industry"])
    ctx = RouteContext(app_id="salesforce", route_id="account-list", env_id="dev", params={})
    raw = loader.get_all("salesforce", "accounts")
    view = shape_list(salesforce, route, ctx, raw)
    assert len(view.records) == len(raw)
    for rec in view.records:
        assert set(rec.keys()) == {"name", "industry"}


def test_shape_list_no_list_fields_returns_full_records(salesforce, loader):
    """Without list_fields, records retain all original keys."""
    route = dataclasses.replace(salesforce.route("account-list"), list_fields=[])
    ctx = RouteContext(app_id="salesforce", route_id="account-list", env_id="dev", params={})
    raw = loader.get_all("salesforce", "accounts")
    view = shape_list(salesforce, route, ctx, raw)
    assert "id" in view.records[0]
    assert "billing_address" in view.records[0]


def test_shape_list_row_urls_parallel_to_records(salesforce, loader):
    """row_urls has the same length as records and each entry is a non-empty URL."""
    route = salesforce.route("account-list")
    ctx = RouteContext(app_id="salesforce", route_id="account-list", env_id="dev", params={})
    raw = loader.get_all("salesforce", "accounts")
    view = shape_list(salesforce, route, ctx, raw)
    assert len(view.row_urls) == len(view.records)
    assert all(url for url in view.row_urls)


def test_shape_list_row_urls_present_after_projection(salesforce, loader):
    """row_urls are still populated correctly when list_fields drops the key field."""
    route = dataclasses.replace(salesforce.route("account-list"), list_fields=["name", "industry"])
    ctx = RouteContext(app_id="salesforce", route_id="account-list", env_id="dev", params={})
    raw = loader.get_all("salesforce", "accounts")
    view = shape_list(salesforce, route, ctx, raw)
    assert len(view.row_urls) == len(view.records)
    assert all(url for url in view.row_urls)
    # projected records do NOT have the key field
    assert "id" not in view.records[0]


# --- related panels ---------------------------------------------------------------


@pytest.fixture(scope="module")
def loader_ng():
    return DataLoader(_DATA_DIR, "default-ng")


def test_shape_detail_related_children(salesforce, loader_ng):
    """Children panel: contacts filtered by account_id == current account PK."""
    # Pick an account that actually has contacts in the dataset
    contacts = loader_ng.get_all("salesforce", "contacts")
    account_id = contacts[0]["account_id"]
    raw = loader_ng.get_record("salesforce", "accounts", "id", account_id)
    route = dataclasses.replace(salesforce.route("account-detail"), related=[
        RelatedConfig(entity="contacts", via="account_id", fields=["first_name", "email"]),
    ])
    ctx = RouteContext(app_id="salesforce", route_id="account-detail", env_id="dev", params={"id": account_id})
    view = shape_detail(salesforce, route, ctx, raw, loader_ng)
    assert len(view.related_panels) == 1
    panel = view.related_panels[0]
    assert panel.entity_title == "Contacts"
    assert panel.fields == ["first_name", "email"]
    assert len(panel.records) > 0
    for rec in panel.records:
        assert set(rec.keys()) == {"first_name", "email"}


def test_shape_detail_related_parent(salesforce, loader_ng):
    """Parent panel: single account loaded via contact.account_id FK."""
    contacts = loader_ng.get_all("salesforce", "contacts")
    contact = next(c for c in contacts if c.get("account_id"))
    route = dataclasses.replace(salesforce.route("contact-detail"), related=[
        RelatedConfig(entity="accounts", from_field="account_id", fields=["name", "industry"]),
    ])
    ctx = RouteContext(app_id="salesforce", route_id="contact-detail", env_id="dev", params={"id": contact["id"]})
    view = shape_detail(salesforce, route, ctx, contact, loader_ng)
    assert len(view.related_panels) == 1
    panel = view.related_panels[0]
    assert panel.entity_title == "Accounts"
    assert len(panel.records) == 1
    assert "name" in panel.records[0]


def test_shape_detail_no_related_config_empty_panels(salesforce, loader_ng):
    """Route with no related config produces empty related_panels."""
    route = dataclasses.replace(salesforce.route("account-detail"), related=[])
    raw = loader_ng.get_record("salesforce", "accounts", "id", "001")
    ctx = RouteContext(app_id="salesforce", route_id="account-detail", env_id="dev", params={"id": "001"})
    view = shape_detail(salesforce, route, ctx, raw, loader_ng)
    assert view.related_panels == []


def test_shape_detail_no_loader_empty_panels(salesforce):
    """Without a loader, related_panels is always empty regardless of route config."""
    route = salesforce.route("account-detail")  # has related config from harness.yaml
    ctx = RouteContext(app_id="salesforce", route_id="account-detail", env_id="dev", params={"id": "001"})
    view = shape_detail(salesforce, route, ctx, {"id": "001"}, loader=None)
    assert view.related_panels == []


# --- collection hydration ---------------------------------------------------------


@pytest.fixture(scope="module")
def sap(apps):
    return next(a for a in apps if a.id == "sap")


@pytest.fixture(scope="module")
def sap_store():
    from src.backend.data_loader import DataLoader as DL
    from src.core.config import parse_shared_entities
    schema = load_schema(_HARNESS_YAML)
    loader = DL(_DATA_DIR, "default-ng")
    store = CanonicalStore()
    shared = parse_shared_entities(_HARNESS_YAML)
    loader.seed(store, schema, shared)
    return store


def test_shape_detail_embeds_line_items(sap, loader_ng, sap_store):
    """SAP order detail assembles order_items as line_items via collection hydration."""
    schema = load_schema(_HARNESS_YAML)
    # Pick an order that has order_items
    order_items = loader_ng.get_all("sap", "order_items") if hasattr(loader_ng, "get_all") else []
    # Use ORD-0001 which is a known anchor record
    raw = loader_ng.get_record("sap", "sales_orders", "order_number", "ORD-0001")
    route = sap.route("shell")
    ctx = RouteContext(app_id="sap", route_id="shell", env_id="dev", params={"sap-client": "100", "so": "ORD-0001"})
    view = shape_detail(sap, route, ctx, raw, loader_ng, schema=schema, store=sap_store)
    assert "line_items" in view.record
    assert isinstance(view.record["line_items"], list)
    assert len(view.record["line_items"]) > 0
    item = view.record["line_items"][0]
    assert "material_number" in item
    assert "quantity" in item
