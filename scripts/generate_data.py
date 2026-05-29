"""
Generate JSON test data for all 12 catalog apps.

Usage:
    just run python scripts/generate_data.py                          # default set, seed=42, count=20
    just run python scripts/generate_data.py --set large --count 200
    just run python scripts/generate_data.py --set dynamic --seed 0   # seed=0 → random

For --set default the anchor IDs from SAMPLE_PARAMS are injected so fixture
params resolve to real records. Other sets are generated purely from seed+count.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from faker import Faker

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.core.sample_params import SAMPLE_PARAMS  # noqa: E402

_GENERATOR = "testharness-webapps/scripts/generate_data.py"
_GENERATOR_VERSION = "1.0.0"

# FK relationships for the default-ng canonical model — used in _metadata.json
_NG_RELATED_ENTITIES = {
    "contacts": [{"field": "account_id", "references": "accounts.id"}],
    "cases": [
        {"field": "account_id", "references": "accounts.id"},
        {"field": "contact_id", "references": "contacts.id"},
    ],
    "contracts": [{"field": "account_id", "references": "accounts.id"}],
    "opportunities": [{"field": "account_id", "references": "accounts.id"}],
    "orders": [
        {"field": "account_id", "references": "accounts.id"},
        {"field": "opportunity_id", "references": "opportunities.id", "nullable": True},
    ],
    "order_items": [
        {"field": "order_id", "references": "orders.id"},
        {"field": "product_id", "references": "products.material_number"},
    ],
    "invoices": [
        {"field": "order_id", "references": "orders.id"},
        {"field": "account_id", "references": "accounts.id"},
    ],
    "leads": [
        {
            "field": "converted_opportunity_id",
            "references": "opportunities.id",
            "nullable": True,
        }
    ],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_INDUSTRIES = [
    "Technology",
    "Finance",
    "Healthcare",
    "Retail",
    "Manufacturing",
    "Energy",
    "Education",
]
_OPP_STAGES = [
    "Prospecting",
    "Qualification",
    "Proposal",
    "Negotiation",
    "Closed Won",
    "Closed Lost",
]
_INC_CATEGORIES = ["Software", "Hardware", "Network", "Security", "Database", "Other"]
_INC_STATES = ["New", "In Progress", "On Hold", "Resolved", "Closed"]
_DEPARTMENTS = [
    "Engineering",
    "Sales",
    "Marketing",
    "Finance",
    "HR",
    "Legal",
    "Operations",
    "Product",
]
_ISSUE_TYPES = ["Bug", "Story", "Task", "Epic", "Sub-task"]
_ISSUE_STATUSES = ["To Do", "In Progress", "In Review", "Done"]
_ISSUE_PRIORITIES = ["Highest", "High", "Medium", "Low", "Lowest"]
_ORDER_STATUSES = ["Open", "In Progress", "Shipped", "Delivered", "Cancelled"]
_PRODUCT_CATEGORIES = ["Hardware", "Software", "Services", "Consumables", "Equipment"]
_INVOICE_STATUSES = ["Draft", "Submitted", "Approved", "Paid", "Overdue", "Cancelled"]
_REGIONS = ["EMEA", "APAC", "AMER", "LATAM"]
_METRICS = ["Revenue", "Units Sold", "Gross Margin", "Customer Count", "Churn Rate"]

# default-ng canonical constants
_NG_OPP_STAGES = (
    ["Closed Won"] * 8
    + ["Proposal/Price Quote"] * 4
    + ["Negotiation/Review"] * 3
    + ["Qualification"] * 3
    + ["Prospecting"] * 2
)
_NG_ORDER_STATUSES = ["Draft"] * 8 + ["Activated"] * 7 + ["Fulfilled"] * 5
_LEAD_STATUSES = ["New", "Working", "Nurturing", "Unqualified"]
_CASE_STATUSES = ["New", "Working", "Escalated", "Closed"]
_CASE_PRIORITIES = ["Low", "Medium", "High", "Critical"]
_CASE_TYPES = ["Question", "Problem", "Feature Request"]
_CASE_ORIGINS = ["Phone", "Email", "Web", "Chat"]
_CONTRACT_STATUSES = ["Draft", "Activated", "Expired"]
_INVOICE_STATUSES_NG = ["Draft", "Sent", "Paid", "Overdue"]
_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-powerpoint": ".pptx",
    "text/plain": ".txt",
}


def _write(path: Path, data: list | dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# CRM — Salesforce + Dynamics 365
# ---------------------------------------------------------------------------


def gen_accounts(fake: Faker, count: int, anchor_id: str | None = None) -> list[dict]:
    def _record(uid: str) -> dict:
        return {
            "id": uid,
            "name": fake.company(),
            "industry": fake.random_element(_INDUSTRIES),
            "phone": fake.phone_number(),
            "billing_address": {
                "street": fake.street_address(),
                "city": fake.city(),
                "state": fake.state_abbr(),
                "zip": fake.zipcode(),
                "country": "US",
            },
            "website": f"https://{fake.domain_name()}",
            "annual_revenue": fake.random_int(min=1, max=500) * 100_000,
            "owner": fake.name(),
        }

    records = [_record(anchor_id)] if anchor_id else []
    for i in range(count - len(records)):
        records.append(_record(f"{i + 2:03d}" if anchor_id else f"{i + 1:03d}"))
    return records


def gen_contacts(fake: Faker, count: int, account_ids: list[str]) -> list[dict]:
    records = []
    for i in range(count):
        first, last = fake.first_name(), fake.last_name()
        records.append(
            {
                "id": f"c{i + 1:03d}",
                "first_name": first,
                "last_name": last,
                "email": f"{first.lower()}.{last.lower()}@{fake.domain_name()}",
                "phone": fake.phone_number(),
                "title": fake.job(),
                "account_id": fake.random_element(account_ids),
            }
        )
    return records


def gen_opportunities(fake: Faker, count: int, account_ids: list[str]) -> list[dict]:
    today = date.today()
    records = []
    for i in range(count):
        records.append(
            {
                "id": f"opp{i + 1:03d}",
                "name": f"{fake.company()} Deal",
                "account_id": fake.random_element(account_ids),
                "amount": fake.random_int(min=2, max=200) * 5_000,
                "stage": fake.random_element(_OPP_STAGES),
                "close_date": today + timedelta(days=fake.random_int(min=-90, max=180)),
                "owner": fake.name(),
            }
        )
    return records


# ---------------------------------------------------------------------------
# ITSM — ServiceNow
# ---------------------------------------------------------------------------


def gen_incidents(fake: Faker, count: int, anchor_sys_id: str | None = None) -> list[dict]:
    def _record(sys_id: str, n: int) -> dict:
        return {
            "sys_id": sys_id,
            "number": f"INC{n:07d}",
            "category": fake.random_element(_INC_CATEGORIES),
            "priority": fake.random_element([1, 2, 3, 4]),
            "short_description": fake.sentence(nb_words=6).rstrip("."),
            "description": fake.paragraph(nb_sentences=3),
            "state": fake.random_element(_INC_STATES),
            "assigned_to": fake.name(),
            "caller": fake.name(),
            "opened_at": fake.iso8601(),
        }

    records = [_record(anchor_sys_id, 1)] if anchor_sys_id else []
    for i in range(count - len(records)):
        sys_id = fake.uuid4().replace("-", "")[:12]
        records.append(_record(sys_id, len(records) + 1))
    return records


# ---------------------------------------------------------------------------
# ERP / Sales — SAP Fiori
# ---------------------------------------------------------------------------


def gen_products(fake: Faker, count: int) -> list[dict]:
    return [
        {
            "material_number": f"MAT{i + 1:04d}",
            "description": fake.catch_phrase(),
            "unit": fake.random_element(["EA", "KG", "LT", "M", "BOX"]),
            "price": fake.pyfloat(min_value=5.0, max_value=9999.0, right_digits=2),
            "currency": "USD",
            "category": fake.random_element(_PRODUCT_CATEGORIES),
        }
        for i in range(count)
    ]


def gen_sales_orders(
    fake: Faker,
    count: int,
    products: list[dict],
    anchor_order_number: str | None = None,
) -> list[dict]:
    def _record(order_number: str) -> dict:
        order_date = date.today() - timedelta(days=fake.random_int(min=0, max=90))
        items = []
        for _ in range(fake.random_int(min=1, max=5)):
            p = fake.random_element(products)
            qty = fake.random_int(min=1, max=50)
            items.append(
                {
                    "material_number": p["material_number"],
                    "description": p["description"],
                    "quantity": qty,
                    "unit_price": p["price"],
                    "total": round(p["price"] * qty, 2),
                }
            )
        return {
            "order_number": order_number,
            "customer_name": fake.company(),
            "order_date": order_date,
            "delivery_date": order_date + timedelta(days=fake.random_int(min=3, max=30)),
            "status": fake.random_element(_ORDER_STATUSES),
            "line_items": items,
            "total": round(sum(i["total"] for i in items), 2),
            "currency": "USD",
        }

    records = [_record(anchor_order_number)] if anchor_order_number else []
    for _ in range(count - len(records)):
        records.append(_record(str(fake.random_int(min=10000, max=99999))))
    return records


# ---------------------------------------------------------------------------
# Finance — Oracle Fusion
# ---------------------------------------------------------------------------


def gen_invoices(fake: Faker, count: int) -> list[dict]:
    records = []
    for i in range(count):
        invoice_date = date.today() - timedelta(days=fake.random_int(min=0, max=120))
        records.append(
            {
                "invoice_number": f"INV-{i + 1:04d}",
                "supplier_name": fake.company(),
                "amount": fake.pyfloat(min_value=500.0, max_value=500_000.0, right_digits=2),
                "currency": fake.random_element(["USD", "EUR", "GBP"]),
                "invoice_date": invoice_date,
                "due_date": invoice_date + timedelta(days=30),
                "gl_account": f"{fake.random_int(min=1000, max=9999)}-{fake.random_int(min=100, max=999)}",
                "status": fake.random_element(_INVOICE_STATUSES),
            }
        )
    return records


# ---------------------------------------------------------------------------
# HR — Workday
# ---------------------------------------------------------------------------


def gen_employees(fake: Faker, count: int) -> list[dict]:
    names = [(fake.first_name(), fake.last_name()) for _ in range(count)]
    manager_pool = [f"{first} {last}" for first, last in names[: max(1, count // 5)]]
    return [
        {
            "employee_id": f"EMP{i + 1:04d}",
            "first_name": first,
            "last_name": last,
            "email": f"{first.lower()}.{last.lower()}@company.com",
            "department": fake.random_element(_DEPARTMENTS),
            "job_title": fake.job(),
            "manager": fake.random_element(manager_pool),
            "hire_date": fake.date_between(start_date="-10y", end_date="today"),
            "location": f"{fake.city()}, {fake.state_abbr()}",
        }
        for i, (first, last) in enumerate(names)
    ]


# ---------------------------------------------------------------------------
# Issue tracking — Jira
# ---------------------------------------------------------------------------

_PROJECT_KEY = "ABC"


def gen_issues(fake: Faker, count: int, anchor_key: str | None = None) -> list[dict]:
    def _record(key: str) -> dict:
        return {
            "key": key,
            "summary": fake.sentence(nb_words=8).rstrip("."),
            "description": fake.paragraph(nb_sentences=4),
            "issue_type": fake.random_element(_ISSUE_TYPES),
            "status": fake.random_element(_ISSUE_STATUSES),
            "priority": fake.random_element(_ISSUE_PRIORITIES),
            "assignee": fake.name(),
            "reporter": fake.name(),
            "created": fake.iso8601(),
            "updated": fake.iso8601(),
            "labels": fake.words(nb=fake.random_int(min=0, max=3)),
            "sprint": f"Sprint {fake.random_int(min=1, max=50)}",
        }

    records = [_record(anchor_key)] if anchor_key else []
    for i in range(count - len(records)):
        records.append(_record(f"{_PROJECT_KEY}-{i + 1}"))
    return records


# ---------------------------------------------------------------------------
# Knowledge — Confluence
# ---------------------------------------------------------------------------


def gen_pages(
    fake: Faker,
    count: int,
    anchor_page_id: str | None = None,
    anchor_space_key: str | None = None,
) -> list[dict]:
    def _record(page_id: str, space_key: str) -> dict:
        return {
            "page_id": page_id,
            "title": fake.sentence(nb_words=5).rstrip("."),
            "space_key": space_key,
            "author": fake.name(),
            "created_date": fake.date_between(start_date="-3y", end_date="-1d"),
            "last_modified": fake.date_between(start_date="-1y", end_date="today"),
            "labels": fake.words(nb=fake.random_int(min=1, max=4)),
            "excerpt": fake.paragraph(nb_sentences=2),
        }

    space = anchor_space_key or "ENG"
    records = [_record(anchor_page_id, space)] if anchor_page_id else []
    for _ in range(count - len(records)):
        records.append(_record(str(fake.random_int(min=10000, max=99999)), space))
    return records


# ---------------------------------------------------------------------------
# Documents — SharePoint
# ---------------------------------------------------------------------------


def gen_documents(fake: Faker, count: int, anchor_site_name: str | None = None) -> list[dict]:
    site = anchor_site_name or "HR"
    records = []
    for i in range(count):
        ct = fake.random_element(list(_CONTENT_TYPES))
        ext = _CONTENT_TYPES[ct]
        records.append(
            {
                "id": f"doc{i + 1:04d}",
                "filename": f"{fake.word().capitalize()}-{fake.random_int(min=2020, max=2026)}{ext}",
                "content_type": ct,
                "author": fake.name(),
                "modified_date": fake.date_between(start_date="-2y", end_date="today"),
                "size_bytes": fake.random_int(min=1024, max=10_485_760),
                "site_name": site,
                "library": "Shared Documents",
            }
        )
    return records


# ---------------------------------------------------------------------------
# Analytics — Power BI + Tableau (shared)
# ---------------------------------------------------------------------------


def gen_sales_metrics(fake: Faker, count: int) -> list[dict]:
    years = [2024, 2025, 2026]
    quarters = ["Q1", "Q2", "Q3", "Q4"]
    return [
        {
            "region": fake.random_element(_REGIONS),
            "period": f"{fake.random_element(years)}-{fake.random_element(quarters)}",
            "metric_name": fake.random_element(_METRICS),
            "value": fake.pyfloat(min_value=1_000.0, max_value=5_000_000.0, right_digits=2),
            "currency": "USD",
        }
        for _ in range(count)
    ]


# ---------------------------------------------------------------------------
# default-ng canonical generators
# ---------------------------------------------------------------------------


def gen_leads(fake: Faker, count: int) -> list[dict]:
    records = []
    for i in range(count):
        first, last = fake.first_name(), fake.last_name()
        records.append({
            "id": f"L{i + 1:03d}",
            "first_name": first,
            "last_name": last,
            "company": fake.company(),
            "email": f"{first.lower()}.{last.lower()}@{fake.domain_name()}",
            "phone": fake.phone_number(),
            "status": fake.random_element(_LEAD_STATUSES),
            "is_converted": False,
            "converted_opportunity_id": None,
        })
    return records


def gen_orders(
    fake: Faker,
    accounts: list[dict],
    closed_won_opps: list[dict],
) -> list[dict]:
    """2–8 orders per account. Closed Won opportunities seed linked orders; rest are renewals."""
    by_account: dict[str, list[dict]] = {}
    for opp in closed_won_opps:
        by_account.setdefault(opp["account_id"], []).append(opp)

    records = []
    counter = 1
    today = date.today()
    for account in accounts:
        acc_id = account["id"]
        n_orders = fake.random_int(min=2, max=8)
        linked_opps = by_account.get(acc_id, [])
        for j in range(n_orders):
            opp = linked_opps[j] if j < len(linked_opps) else None
            status = fake.random_element(_NG_ORDER_STATUSES)
            effective = today - timedelta(days=fake.random_int(min=30, max=365))
            if opp:
                total_amount = round(opp["amount"] * fake.pyfloat(min_value=0.80, max_value=0.99, right_digits=2), 2)
            else:
                total_amount = round(fake.random_int(min=5, max=150) * 1_000.0, 2)
            records.append({
                "id": f"ORD-{counter:04d}",
                "account_id": acc_id,
                "opportunity_id": opp["id"] if opp else None,
                "status": status,
                "total_amount": total_amount,
                "effective_date": effective,
                "end_date": effective + timedelta(days=fake.random_int(min=90, max=730)),
            })
            counter += 1
    return records


def gen_order_items(
    fake: Faker,
    orders: list[dict],
    products: list[dict],
) -> list[dict]:
    records = []
    counter = 1
    for order in orders:
        n_items = fake.random_int(min=2, max=4)
        for _ in range(n_items):
            product = fake.random_element(products)
            qty = fake.random_int(min=1, max=20)
            unit_price = round(product["price"], 2)
            records.append({
                "id": f"OI-{counter:05d}",
                "order_id": order["id"],
                "product_id": product["material_number"],
                "quantity": qty,
                "unit_price": unit_price,
                "total_price": round(unit_price * qty, 2),
            })
            counter += 1
    return records


def gen_contracts(fake: Faker, count: int, account_ids: list[str]) -> list[dict]:
    records = []
    today = date.today()
    for i in range(count):
        start = today - timedelta(days=fake.random_int(min=0, max=730))
        term = fake.random_element([12, 24, 36])
        records.append({
            "id": f"CON-{i + 1:04d}",
            "account_id": fake.random_element(account_ids),
            "start_date": start,
            "end_date": start + timedelta(days=term * 30),
            "status": fake.random_element(_CONTRACT_STATUSES),
            "contract_term_months": term,
            "total_amount": round(fake.random_int(min=10, max=500) * 1_000.0, 2),
        })
    return records


def gen_cases(
    fake: Faker,
    count: int,
    account_ids: list[str],
    contact_ids: list[str],
) -> list[dict]:
    records = []
    for i in range(count):
        is_closed = fake.random_element([True, False, False])
        records.append({
            "id": f"CASE-{i + 1:05d}",
            "account_id": fake.random_element(account_ids),
            "contact_id": fake.random_element(contact_ids),
            "subject": fake.sentence(nb_words=7).rstrip("."),
            "status": "Closed" if is_closed else fake.random_element(_CASE_STATUSES[:-1]),
            "priority": fake.random_element(_CASE_PRIORITIES),
            "type": fake.random_element(_CASE_TYPES),
            "origin": fake.random_element(_CASE_ORIGINS),
            "is_closed": is_closed,
        })
    return records


def gen_invoices_canonical(fake: Faker, fulfilled_orders: list[dict]) -> list[dict]:
    """1–2 invoices per fulfilled order. Each invoice amount < order total_amount."""
    records = []
    counter = 1
    today = date.today()
    for order in fulfilled_orders:
        n_invoices = fake.random_int(min=1, max=2)
        for k in range(n_invoices):
            fraction = fake.pyfloat(min_value=0.35, max_value=0.55, right_digits=2)
            amount = round(order["total_amount"] * fraction, 2)
            issue_date = today - timedelta(days=fake.random_int(min=10, max=120))
            status = fake.random_element(_INVOICE_STATUSES_NG)
            records.append({
                "id": f"INV-{counter:04d}",
                "order_id": order["id"],
                "account_id": order["account_id"],
                "amount": amount,
                "currency": "USD",
                "status": status,
                "issue_date": issue_date,
                "due_date": issue_date + timedelta(days=30),
                "paid_date": issue_date + timedelta(days=fake.random_int(min=1, max=25))
                if status == "Paid" else None,
            })
            counter += 1
    return records


# ---------------------------------------------------------------------------
# default-ng projection functions (canonical → app field names)
# ---------------------------------------------------------------------------


def project_sap_orders(orders: list[dict]) -> list[dict]:
    return [
        {
            "order_number": o["id"],
            "account_id": o["account_id"],
            "opportunity_id": o["opportunity_id"],
            "status": o["status"],
            "total": o["total_amount"],
            "effective_date": o["effective_date"],
            "end_date": o["end_date"],
        }
        for o in orders
    ]


def project_sap_order_items(order_items: list[dict]) -> list[dict]:
    return [
        {
            "id": oi["id"],
            "order_number": oi["order_id"],
            "material_number": oi["product_id"],
            "quantity": oi["quantity"],
            "price_per_unit": oi["unit_price"],
            "total_price": oi["total_price"],
        }
        for oi in order_items
    ]


def project_servicenow_incidents(cases: list[dict]) -> list[dict]:
    priority_map = {"Low": 4, "Medium": 3, "High": 2, "Critical": 1}
    category_map = {"Question": "inquiry", "Problem": "software", "Feature Request": "enhancement"}
    return [
        {
            "sys_id": c["id"].lower().replace("-", ""),
            "number": f"INC{int(c['id'].split('-')[1]):07d}",
            "account_id": c["account_id"],
            "contact_id": c["contact_id"],
            "short_description": c["subject"],
            "state": "Closed" if c["is_closed"] else c["status"],
            "priority": priority_map.get(c["priority"], 3),
            "category": category_map.get(c["type"], "other"),
            "origin": c["origin"].lower(),
        }
        for c in cases
    ]


def project_oracle_invoices(invoices: list[dict]) -> list[dict]:
    return [
        {
            "invoice_number": inv["id"],
            "order_id": inv["order_id"],
            "account_id": inv["account_id"],
            "amount": inv["amount"],
            "currency": inv["currency"],
            "invoice_date": inv["issue_date"],
            "due_date": inv["due_date"],
            "paid_date": inv["paid_date"],
            "status": inv["status"],
        }
        for inv in invoices
    ]


# ---------------------------------------------------------------------------
# default-ng BI aggregation functions
# ---------------------------------------------------------------------------


def agg_pipeline(opportunities: list[dict]) -> list[dict]:
    from collections import defaultdict
    by_stage: dict[str, dict] = defaultdict(lambda: {"count": 0, "total_amount": 0.0})
    for opp in opportunities:
        s = opp["stage"]
        by_stage[s]["count"] += 1
        by_stage[s]["total_amount"] += opp["amount"]
    return [
        {"stage": stage, "count": v["count"], "total_amount": round(v["total_amount"], 2)}
        for stage, v in sorted(by_stage.items())
    ]


def agg_revenue(orders: list[dict]) -> list[dict]:
    from collections import defaultdict
    by_quarter: dict[str, dict] = defaultdict(lambda: {"order_count": 0, "revenue": 0.0})
    for order in orders:
        if order["status"] != "Fulfilled":
            continue
        d = order["effective_date"]
        if isinstance(d, str):
            d = date.fromisoformat(d)
        q = f"{d.year}-Q{(d.month - 1) // 3 + 1}"
        by_quarter[q]["order_count"] += 1
        by_quarter[q]["revenue"] += order["total_amount"]
    return [
        {"quarter": q, "order_count": v["order_count"], "revenue": round(v["revenue"], 2)}
        for q, v in sorted(by_quarter.items())
    ]


# ---------------------------------------------------------------------------
# default-ng two-pass orchestrator
# ---------------------------------------------------------------------------


def generate_default_ng(fake: Faker, count: int, root: Path) -> None:
    # Pass 1: canonical
    accounts = gen_accounts(fake, count)
    account_ids = [a["id"] for a in accounts]

    contacts = gen_contacts(fake, count, account_ids)
    contact_ids = [c["id"] for c in contacts]

    products = gen_products(fake, count)

    leads = gen_leads(fake, count // 2)

    opportunities = [
        {**opp, "stage": _NG_OPP_STAGES[i % len(_NG_OPP_STAGES)]}
        for i, opp in enumerate(gen_opportunities(fake, count, account_ids))
    ]
    closed_won_opps = [o for o in opportunities if o["stage"] == "Closed Won"]

    orders = gen_orders(fake, accounts, closed_won_opps)
    order_items = gen_order_items(fake, orders, products)
    contracts = gen_contracts(fake, 6, account_ids)
    cases = gen_cases(fake, count, account_ids, contact_ids)
    fulfilled_orders = [o for o in orders if o["status"] == "Fulfilled"]
    invoices = gen_invoices_canonical(fake, fulfilled_orders)

    # Link 4 leads to Closed Won opportunities
    for i, lead in enumerate(leads[:4]):
        if i < len(closed_won_opps):
            lead["is_converted"] = True
            lead["converted_opportunity_id"] = closed_won_opps[i]["id"]

    canonical = root / "_canonical"
    _write(canonical / "accounts.json", accounts)
    _write(canonical / "contacts.json", contacts)
    _write(canonical / "leads.json", leads)
    _write(canonical / "products.json", products)
    _write(canonical / "opportunities.json", opportunities)
    _write(canonical / "orders.json", orders)
    _write(canonical / "order_items.json", order_items)
    _write(canonical / "contracts.json", contracts)
    _write(canonical / "cases.json", cases)
    _write(canonical / "invoices.json", invoices)

    # Pass 2: app projections
    _write(root / "salesforce" / "accounts.json", accounts)
    _write(root / "salesforce" / "contacts.json", contacts)
    _write(root / "salesforce" / "leads.json", leads)
    _write(root / "salesforce" / "opportunities.json", opportunities)
    _write(root / "salesforce" / "cases.json", cases)

    _write(root / "dynamics" / "accounts.json", accounts)
    _write(root / "dynamics" / "contacts.json", contacts)
    _write(root / "dynamics" / "opportunities.json", opportunities)

    _write(root / "sap" / "products.json", products)
    _write(root / "sap" / "sales_orders.json", project_sap_orders(orders))
    _write(root / "sap" / "order_items.json", project_sap_order_items(order_items))

    _write(root / "oracle" / "invoices.json", project_oracle_invoices(invoices))

    _write(root / "servicenow" / "incidents.json", project_servicenow_incidents(cases))

    _write(root / "workday" / "employees.json", gen_employees(fake, count))

    # Pass 3: BI aggregations
    pipeline = agg_pipeline(opportunities)
    revenue = agg_revenue(orders)
    _write(root / "tableau" / "pipeline_by_stage.json", pipeline)
    _write(root / "tableau" / "revenue_by_quarter.json", revenue)
    _write(root / "power-bi" / "pipeline_by_stage.json", pipeline)
    _write(root / "power-bi" / "revenue_by_quarter.json", revenue)

    # Metadata
    metadata = {
        "generator": _GENERATOR,
        "version": _GENERATOR_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dataset": "default-ng",
        "related_entities": _NG_RELATED_ENTITIES,
    }
    _write(root / "_canonical" / "_metadata.json", metadata)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


_KNOWN_APPS = frozenset({
    "salesforce", "dynamics", "servicenow", "sap", "oracle",
    "workday", "jira", "confluence", "sharepoint", "power-bi", "tableau", "power-apps",
})


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate JSON test data for catalog apps.")
    parser.add_argument(
        "--set",
        default="default",
        dest="set_name",
        metavar="NAME",
        help="Output set name (default: default)",
    )
    parser.add_argument("--seed", type=int, default=42, help="Faker seed; 0 = random (default: 42)")
    parser.add_argument("--count", type=int, default=20, help="Records per entity (default: 20)")
    parser.add_argument("--app", default=None, metavar="APP_ID", help="Seed only this app id (default: all)")
    args = parser.parse_args()

    if args.app and args.app not in _KNOWN_APPS:
        sys.exit(f"Unknown app: {args.app!r}")

    def _gen(app_id: str) -> bool:
        return args.app is None or args.app == app_id

    seed = random.randint(1, 999_999) if args.seed == 0 else args.seed
    anchors = SAMPLE_PARAMS if args.set_name == "default" else {}

    fake = Faker()
    Faker.seed(seed)

    root = Path(__file__).parent.parent / "data" / args.set_name

    if args.set_name == "default-ng":
        generate_default_ng(fake, args.count, root)
        return

    # CRM — Salesforce
    if _gen("salesforce"):
        sf_accounts = gen_accounts(fake, args.count, anchor_id=anchors.get("id"))
        sf_ids = [a["id"] for a in sf_accounts]
        _write(root / "salesforce" / "accounts.json", sf_accounts)
        _write(root / "salesforce" / "contacts.json", gen_contacts(fake, args.count, sf_ids))
        _write(root / "salesforce" / "opportunities.json", gen_opportunities(fake, args.count, sf_ids))

    # CRM — Dynamics 365 (same domain, independent records)
    if _gen("dynamics"):
        dyn_accounts = gen_accounts(fake, args.count, anchor_id=anchors.get("id"))
        dyn_ids = [a["id"] for a in dyn_accounts]
        _write(root / "dynamics" / "accounts.json", dyn_accounts)
        _write(root / "dynamics" / "contacts.json", gen_contacts(fake, args.count, dyn_ids))
        _write(root / "dynamics" / "opportunities.json", gen_opportunities(fake, args.count, dyn_ids))

    # ITSM — ServiceNow
    if _gen("servicenow"):
        _write(
            root / "servicenow" / "incidents.json",
            gen_incidents(fake, args.count, anchor_sys_id=anchors.get("sys_id")),
        )

    # ERP / Sales — SAP
    if _gen("sap"):
        products = gen_products(fake, args.count)
        _write(root / "sap" / "products.json", products)
        _write(
            root / "sap" / "sales_orders.json",
            gen_sales_orders(fake, args.count, products, anchor_order_number=anchors.get("so")),
        )

    # Finance — Oracle
    if _gen("oracle"):
        _write(root / "oracle" / "invoices.json", gen_invoices(fake, args.count))

    # HR — Workday
    if _gen("workday"):
        _write(root / "workday" / "employees.json", gen_employees(fake, args.count))

    # Issue tracking — Jira
    if _gen("jira"):
        _write(
            root / "jira" / "issues.json",
            gen_issues(fake, args.count, anchor_key=anchors.get("issue_key")),
        )

    # Knowledge — Confluence
    if _gen("confluence"):
        _write(
            root / "confluence" / "pages.json",
            gen_pages(
                fake,
                args.count,
                anchor_page_id=anchors.get("page_id"),
                anchor_space_key=anchors.get("space_key"),
            ),
        )

    # Documents — SharePoint
    if _gen("sharepoint"):
        _write(
            root / "sharepoint" / "documents.json",
            gen_documents(fake, args.count, anchor_site_name=anchors.get("site_name")),
        )

    # Analytics — Power BI + Tableau (shared metrics, 4× count for BI row volume)
    if _gen("power-bi") or _gen("tableau"):
        metrics = gen_sales_metrics(fake, args.count * 4)
        if _gen("power-bi"):
            _write(root / "power-bi" / "sales_metrics.json", metrics)
        if _gen("tableau"):
            _write(root / "tableau" / "sales_metrics.json", metrics)

    # LOB orders — Power Apps (reuses sales order model)
    if _gen("power-apps"):
        pa_products = gen_products(fake, args.count)
        _write(
            root / "power-apps" / "sales_orders.json",
            gen_sales_orders(fake, args.count, pa_products, anchor_order_number=anchors.get("so")),
        )


if __name__ == "__main__":
    main()
