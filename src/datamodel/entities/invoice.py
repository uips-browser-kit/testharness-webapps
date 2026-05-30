from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import ClassVar

from pydantic import BaseModel


class Invoice(BaseModel):
    """Canonical field names differ from some data files:
    - canonical/invoices.json uses id (→ invoice_number); DataLoader remaps on load.
    - oracle/invoices.json uses invoice_number directly (matches this model).
    """

    __business_key__: ClassVar[str] = "invoice_number"

    invoice_number: str
    order_id: str | None = None
    account_id: str
    amount: Decimal
    currency: str
    status: str
    issue_date: date
    due_date: date
    paid_date: date | None = None
