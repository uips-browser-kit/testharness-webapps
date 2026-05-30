from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import ClassVar

from pydantic import BaseModel


class Order(BaseModel):
    """Canonical field names differ from some data files:
    - canonical/orders.json uses id (→ order_number), effective_date (→ order_date),
      end_date (→ delivery_date), total_amount (→ total_amount); DataLoader remaps on load.
    - sap/sales_orders.json uses order_number, effective_date, end_date, total; task #142
      will rename those fields to match.
    """

    __business_key__: ClassVar[str] = "order_number"

    order_number: str
    account_id: str
    opportunity_id: str | None = None
    status: str
    total_amount: Decimal
    currency: str
    order_date: date
    delivery_date: date | None = None
