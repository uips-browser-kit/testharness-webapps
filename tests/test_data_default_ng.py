"""
FK consistency and amount chain tests for the default-ng canonical dataset.
Generates the dataset fresh before running so tests are always against current code.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from faker import Faker

# ---------------------------------------------------------------------------
# Dataset generation fixture
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent.parent / "data" / "default-ng"
_CANONICAL = _DATA_DIR / "_canonical"

import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.generate_data import _NG_OPP_STAGES, generate_default_ng  # noqa: E402

_COUNT = 20
_CONTRACTS_COUNT = 6  # gen_contracts is called with a fixed count of 6 in generate_default_ng
_CLOSED_WON_COUNT = sum(1 for s in _NG_OPP_STAGES if s == "Closed Won")


@pytest.fixture(scope="module", autouse=True)
def generated_dataset():
    """Generate default-ng dataset once for the module."""
    fake = Faker()
    Faker.seed(42)
    generate_default_ng(fake, _COUNT, _DATA_DIR)


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def accounts(generated_dataset):
    return _load(_CANONICAL / "accounts.json")


@pytest.fixture(scope="module")
def contacts(generated_dataset):
    return _load(_CANONICAL / "contacts.json")


@pytest.fixture(scope="module")
def leads(generated_dataset):
    return _load(_CANONICAL / "leads.json")


@pytest.fixture(scope="module")
def products(generated_dataset):
    return _load(_CANONICAL / "products.json")


@pytest.fixture(scope="module")
def opportunities(generated_dataset):
    return _load(_CANONICAL / "opportunities.json")


@pytest.fixture(scope="module")
def orders(generated_dataset):
    return _load(_CANONICAL / "orders.json")


@pytest.fixture(scope="module")
def order_items(generated_dataset):
    return _load(_CANONICAL / "order_items.json")


@pytest.fixture(scope="module")
def contracts(generated_dataset):
    return _load(_CANONICAL / "contracts.json")


@pytest.fixture(scope="module")
def cases(generated_dataset):
    return _load(_CANONICAL / "cases.json")


@pytest.fixture(scope="module")
def invoices(generated_dataset):
    return _load(_CANONICAL / "invoices.json")


# ---------------------------------------------------------------------------
# Canonical counts
# ---------------------------------------------------------------------------

def test_accounts_count(accounts):
    assert len(accounts) == _COUNT


def test_contacts_count(contacts):
    assert len(contacts) == _COUNT


def test_opportunities_count(opportunities):
    assert len(opportunities) == _COUNT


def test_products_count(products):
    assert len(products) == _COUNT


def test_cases_count(cases):
    assert len(cases) == _COUNT


def test_leads_nonempty(leads):
    assert len(leads) > 0


def test_contracts_count(contracts):
    assert len(contracts) == _CONTRACTS_COUNT


def test_orders_nonempty(orders):
    assert len(orders) > 0


def test_order_items_nonempty(order_items):
    assert len(order_items) > 0


def test_invoices_nonempty(invoices):
    assert len(invoices) > 0


# ---------------------------------------------------------------------------
# FK: contacts → accounts
# ---------------------------------------------------------------------------

def test_contacts_account_fk(contacts, accounts):
    account_ids = {a["id"] for a in accounts}
    for c in contacts:
        assert c["account_id"] in account_ids, f"Contact {c['id']} has orphan account_id {c['account_id']!r}"


# ---------------------------------------------------------------------------
# FK: cases → accounts + contacts
# ---------------------------------------------------------------------------

def test_cases_account_fk(cases, accounts):
    account_ids = {a["id"] for a in accounts}
    for c in cases:
        assert c["account_id"] in account_ids, f"Case {c['id']} has orphan account_id {c['account_id']!r}"


def test_cases_contact_fk(cases, contacts):
    contact_ids = {c["id"] for c in contacts}
    for c in cases:
        assert c["contact_id"] in contact_ids, f"Case {c['id']} has orphan contact_id {c['contact_id']!r}"


# ---------------------------------------------------------------------------
# FK: contracts → accounts
# ---------------------------------------------------------------------------

def test_contracts_account_fk(contracts, accounts):
    account_ids = {a["id"] for a in accounts}
    for c in contracts:
        assert c["account_id"] in account_ids


# ---------------------------------------------------------------------------
# FK: opportunities → accounts
# ---------------------------------------------------------------------------

def test_opportunities_account_fk(opportunities, accounts):
    account_ids = {a["id"] for a in accounts}
    for o in opportunities:
        assert o["account_id"] in account_ids


# ---------------------------------------------------------------------------
# Opportunity stage distribution
# ---------------------------------------------------------------------------

def test_opportunities_have_closed_won(opportunities):
    closed_won = [o for o in opportunities if o["stage"] == "Closed Won"]
    assert len(closed_won) == _CLOSED_WON_COUNT


def test_opportunities_stage_variety(opportunities):
    stages = {o["stage"] for o in opportunities}
    assert len(stages) >= 3


# ---------------------------------------------------------------------------
# FK: orders → accounts + opportunities
# ---------------------------------------------------------------------------

def test_orders_account_fk(orders, accounts):
    account_ids = {a["id"] for a in accounts}
    for o in orders:
        assert o["account_id"] in account_ids, f"Order {o['id']} has orphan account_id"


def test_orders_opportunity_fk(orders, opportunities):
    opp_ids = {o["id"] for o in opportunities}
    closed_won_ids = {o["id"] for o in opportunities if o["stage"] == "Closed Won"}
    for order in orders:
        if order["opportunity_id"] is not None:
            assert order["opportunity_id"] in opp_ids, f"Order {order['id']} references unknown opportunity"
            assert order["opportunity_id"] in closed_won_ids, f"Order {order['id']} linked to non-Closed-Won opportunity"


# ---------------------------------------------------------------------------
# Orders per account: 2–8
# ---------------------------------------------------------------------------

def test_orders_per_account_in_range(orders, accounts):
    from collections import Counter
    counts = Counter(o["account_id"] for o in orders)
    for acc_id in (a["id"] for a in accounts):
        n = counts.get(acc_id, 0)
        assert 2 <= n <= 8, f"Account {acc_id} has {n} orders (expected 2–8)"


# ---------------------------------------------------------------------------
# FK: order_items → orders + products
# ---------------------------------------------------------------------------

def test_order_items_order_fk(order_items, orders):
    order_ids = {o["id"] for o in orders}
    for oi in order_items:
        assert oi["order_id"] in order_ids, f"OrderItem {oi['id']} has orphan order_id"


def test_order_items_product_fk(order_items, products):
    product_ids = {p["material_number"] for p in products}
    for oi in order_items:
        assert oi["product_id"] in product_ids, f"OrderItem {oi['id']} has orphan product_id"


def test_order_items_per_order_in_range(order_items, orders):
    from collections import Counter
    counts = Counter(oi["order_id"] for oi in order_items)
    for order in orders:
        n = counts.get(order["id"], 0)
        assert 2 <= n <= 4, f"Order {order['id']} has {n} items (expected 2–4)"


# ---------------------------------------------------------------------------
# FK: invoices → fulfilled orders + accounts
# ---------------------------------------------------------------------------

def test_invoices_order_fk(invoices, orders):
    order_ids = {o["id"] for o in orders}
    for inv in invoices:
        assert inv["order_id"] in order_ids, f"Invoice {inv['id']} has orphan order_id"


def test_invoices_only_for_fulfilled_orders(invoices, orders):
    fulfilled_ids = {o["id"] for o in orders if o["status"] == "Fulfilled"}
    for inv in invoices:
        assert inv["order_id"] in fulfilled_ids, f"Invoice {inv['id']} references non-Fulfilled order"


def test_invoices_account_fk(invoices, accounts):
    account_ids = {a["id"] for a in accounts}
    for inv in invoices:
        assert inv["account_id"] in account_ids, f"Invoice {inv['id']} has orphan account_id"


# ---------------------------------------------------------------------------
# Amount chain: invoice < order < opportunity (for linked records)
# ---------------------------------------------------------------------------

def test_invoice_amount_less_than_order(invoices, orders):
    order_by_id = {o["id"]: o for o in orders}
    for inv in invoices:
        order = order_by_id[inv["order_id"]]
        assert inv["amount"] < order["total_amount"], (
            f"Invoice {inv['id']} amount {inv['amount']} >= order {order['id']} total {order['total_amount']}"
        )


def test_order_amount_less_than_opportunity(orders, opportunities):
    opp_by_id = {o["id"]: o for o in opportunities}
    for order in orders:
        if order["opportunity_id"] is None:
            continue
        opp = opp_by_id[order["opportunity_id"]]
        assert order["total_amount"] < opp["amount"], (
            f"Order {order['id']} total {order['total_amount']} >= opportunity {opp['id']} amount {opp['amount']}"
        )


# ---------------------------------------------------------------------------
# Leads: converted leads reference Closed Won opportunities
# ---------------------------------------------------------------------------

def test_converted_leads_count(leads):
    converted = [l for l in leads if l["is_converted"]]
    assert len(converted) == 4


def test_converted_leads_have_opportunity_id(leads, opportunities):
    opp_ids = {o["id"] for o in opportunities}
    for lead in leads:
        if lead["is_converted"]:
            assert lead["converted_opportunity_id"] is not None
            assert lead["converted_opportunity_id"] in opp_ids


# ---------------------------------------------------------------------------
# App projections: oracle invoices have account_id and order_id
# ---------------------------------------------------------------------------

def test_oracle_invoices_have_account_id():
    oracle_invoices = _load(_DATA_DIR / "oracle" / "invoices.json")
    for inv in oracle_invoices:
        assert "account_id" in inv
        assert "order_id" in inv


def test_sap_orders_have_account_id():
    sap_orders = _load(_DATA_DIR / "sap" / "sales_orders.json")
    for o in sap_orders:
        assert "account_id" in o


def test_servicenow_incidents_have_account_id():
    incidents = _load(_DATA_DIR / "servicenow" / "incidents.json")
    for inc in incidents:
        assert "account_id" in inc


# ---------------------------------------------------------------------------
# Salesforce and Dynamics share the same account IDs
# ---------------------------------------------------------------------------

def test_salesforce_dynamics_share_account_ids():
    sf = {a["id"] for a in _load(_DATA_DIR / "salesforce" / "accounts.json")}
    dyn = {a["id"] for a in _load(_DATA_DIR / "dynamics" / "accounts.json")}
    assert sf == dyn


# ---------------------------------------------------------------------------
# BI aggregations are non-empty
# ---------------------------------------------------------------------------

def test_pipeline_by_stage_nonempty():
    data = _load(_DATA_DIR / "tableau" / "pipeline_by_stage.json")
    assert len(data) > 0
    assert all("stage" in r and "count" in r and "total_amount" in r for r in data)


def test_revenue_by_quarter_nonempty():
    data = _load(_DATA_DIR / "tableau" / "revenue_by_quarter.json")
    assert len(data) > 0
    assert all("quarter" in r and "revenue" in r for r in data)


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def test_metadata_file_exists():
    assert (_CANONICAL / "_metadata.json").exists()


def test_metadata_required_keys():
    meta = json.loads((_CANONICAL / "_metadata.json").read_text(encoding="utf-8"))
    for key in ("generator", "version", "generated_at", "dataset", "related_entities"):
        assert key in meta, f"_metadata.json missing key: {key!r}"


def test_metadata_dataset_name():
    meta = json.loads((_CANONICAL / "_metadata.json").read_text(encoding="utf-8"))
    assert meta["dataset"] == "default-ng"


def test_metadata_related_entities_covers_fks():
    meta = json.loads((_CANONICAL / "_metadata.json").read_text(encoding="utf-8"))
    rels = meta["related_entities"]
    assert "contacts" in rels
    assert "orders" in rels
    assert "invoices" in rels
    assert "order_items" in rels
    # every entry has field + references
    for entity, links in rels.items():
        for link in links:
            assert "field" in link, f"{entity} link missing 'field'"
            assert "references" in link, f"{entity} link missing 'references'"


def test_metadata_generated_at_is_iso8601():
    from datetime import datetime
    meta = json.loads((_CANONICAL / "_metadata.json").read_text(encoding="utf-8"))
    ts = meta["generated_at"]
    datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
