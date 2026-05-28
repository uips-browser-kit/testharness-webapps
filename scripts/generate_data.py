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
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

sys.path.insert(0, str(Path(__file__).parent))
from catalog_urls import SAMPLE_PARAMS  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_INDUSTRIES = ["Technology", "Finance", "Healthcare", "Retail", "Manufacturing", "Energy", "Education"]
_OPP_STAGES = ["Prospecting", "Qualification", "Proposal", "Negotiation", "Closed Won", "Closed Lost"]
_INC_CATEGORIES = ["Software", "Hardware", "Network", "Security", "Database", "Other"]
_INC_STATES = ["New", "In Progress", "On Hold", "Resolved", "Closed"]
_DEPARTMENTS = ["Engineering", "Sales", "Marketing", "Finance", "HR", "Legal", "Operations", "Product"]
_ISSUE_TYPES = ["Bug", "Story", "Task", "Epic", "Sub-task"]
_ISSUE_STATUSES = ["To Do", "In Progress", "In Review", "Done"]
_ISSUE_PRIORITIES = ["Highest", "High", "Medium", "Low", "Lowest"]
_ORDER_STATUSES = ["Open", "In Progress", "Shipped", "Delivered", "Cancelled"]
_PRODUCT_CATEGORIES = ["Hardware", "Software", "Services", "Consumables", "Equipment"]
_INVOICE_STATUSES = ["Draft", "Submitted", "Approved", "Paid", "Overdue", "Cancelled"]
_REGIONS = ["EMEA", "APAC", "AMER", "LATAM"]
_METRICS = ["Revenue", "Units Sold", "Gross Margin", "Customer Count", "Churn Rate"]
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
        records.append({
            "id": f"c{i + 1:03d}",
            "first_name": first,
            "last_name": last,
            "email": f"{first.lower()}.{last.lower()}@{fake.domain_name()}",
            "phone": fake.phone_number(),
            "title": fake.job(),
            "account_id": fake.random_element(account_ids),
        })
    return records


def gen_opportunities(fake: Faker, count: int, account_ids: list[str]) -> list[dict]:
    today = date.today()
    records = []
    for i in range(count):
        records.append({
            "id": f"opp{i + 1:03d}",
            "name": f"{fake.company()} Deal",
            "account_id": fake.random_element(account_ids),
            "amount": fake.random_int(min=2, max=200) * 5_000,
            "stage": fake.random_element(_OPP_STAGES),
            "close_date": today + timedelta(days=fake.random_int(min=-90, max=180)),
            "owner": fake.name(),
        })
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
            items.append({
                "material_number": p["material_number"],
                "description": p["description"],
                "quantity": qty,
                "unit_price": p["price"],
                "total": round(p["price"] * qty, 2),
            })
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
        records.append({
            "invoice_number": f"INV-{i + 1:04d}",
            "supplier_name": fake.company(),
            "amount": fake.pyfloat(min_value=500.0, max_value=500_000.0, right_digits=2),
            "currency": fake.random_element(["USD", "EUR", "GBP"]),
            "invoice_date": invoice_date,
            "due_date": invoice_date + timedelta(days=30),
            "gl_account": f"{fake.random_int(min=1000, max=9999)}-{fake.random_int(min=100, max=999)}",
            "status": fake.random_element(_INVOICE_STATUSES),
        })
    return records


# ---------------------------------------------------------------------------
# HR — Workday
# ---------------------------------------------------------------------------

def gen_employees(fake: Faker, count: int) -> list[dict]:
    names = [(fake.first_name(), fake.last_name()) for _ in range(count)]
    manager_pool = [f"{f} {l}" for f, l in names[: max(1, count // 5)]]
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
        records.append({
            "id": f"doc{i + 1:04d}",
            "filename": f"{fake.word().capitalize()}-{fake.random_int(min=2020, max=2026)}{ext}",
            "content_type": ct,
            "author": fake.name(),
            "modified_date": fake.date_between(start_date="-2y", end_date="today"),
            "size_bytes": fake.random_int(min=1024, max=10_485_760),
            "site_name": site,
            "library": "Shared Documents",
        })
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
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate JSON test data for catalog apps.")
    parser.add_argument("--set", default="default", dest="set_name", metavar="NAME",
                        help="Output set name (default: default)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Faker seed; 0 = random (default: 42)")
    parser.add_argument("--count", type=int, default=20,
                        help="Records per entity (default: 20)")
    args = parser.parse_args()

    seed = random.randint(1, 999_999) if args.seed == 0 else args.seed
    anchors = SAMPLE_PARAMS if args.set_name == "default" else {}

    fake = Faker()
    Faker.seed(seed)

    root = Path(__file__).parent.parent / "data" / args.set_name

    # CRM — Salesforce
    sf_accounts = gen_accounts(fake, args.count, anchor_id=anchors.get("id"))
    sf_ids = [a["id"] for a in sf_accounts]
    _write(root / "salesforce" / "accounts.json",     sf_accounts)
    _write(root / "salesforce" / "contacts.json",     gen_contacts(fake, args.count, sf_ids))
    _write(root / "salesforce" / "opportunities.json", gen_opportunities(fake, args.count, sf_ids))

    # CRM — Dynamics 365 (same domain, independent records)
    dyn_accounts = gen_accounts(fake, args.count, anchor_id=anchors.get("id"))
    dyn_ids = [a["id"] for a in dyn_accounts]
    _write(root / "dynamics" / "accounts.json",      dyn_accounts)
    _write(root / "dynamics" / "contacts.json",      gen_contacts(fake, args.count, dyn_ids))
    _write(root / "dynamics" / "opportunities.json", gen_opportunities(fake, args.count, dyn_ids))

    # ITSM — ServiceNow
    _write(root / "servicenow" / "incidents.json",
           gen_incidents(fake, args.count, anchor_sys_id=anchors.get("sys_id")))

    # ERP / Sales — SAP
    products = gen_products(fake, args.count)
    _write(root / "sap" / "products.json",     products)
    _write(root / "sap" / "sales_orders.json",
           gen_sales_orders(fake, args.count, products, anchor_order_number=anchors.get("so")))

    # Finance — Oracle
    _write(root / "oracle" / "invoices.json", gen_invoices(fake, args.count))

    # HR — Workday
    _write(root / "workday" / "employees.json", gen_employees(fake, args.count))

    # Issue tracking — Jira
    _write(root / "jira" / "issues.json",
           gen_issues(fake, args.count, anchor_key=anchors.get("issue_key")))

    # Knowledge — Confluence
    _write(root / "confluence" / "pages.json",
           gen_pages(fake, args.count,
                     anchor_page_id=anchors.get("page_id"),
                     anchor_space_key=anchors.get("space_key")))

    # Documents — SharePoint
    _write(root / "sharepoint" / "documents.json",
           gen_documents(fake, args.count, anchor_site_name=anchors.get("site_name")))

    # Analytics — Power BI + Tableau (shared metrics, 4× count for BI row volume)
    metrics = gen_sales_metrics(fake, args.count * 4)
    _write(root / "power-bi" / "sales_metrics.json",  metrics)
    _write(root / "tableau"  / "sales_metrics.json",  metrics)

    # LOB orders — Power Apps (reuses sales order model)
    pa_products = gen_products(fake, args.count)
    _write(root / "power-apps" / "sales_orders.json",
           gen_sales_orders(fake, args.count, pa_products, anchor_order_number=anchors.get("so")))


if __name__ == "__main__":
    main()
