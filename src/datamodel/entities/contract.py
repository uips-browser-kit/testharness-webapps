from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import ClassVar

from pydantic import BaseModel


class Contract(BaseModel):
    __business_key__: ClassVar[str] = "id"

    id: str
    account_id: str
    start_date: date
    end_date: date | None = None
    status: str
    contract_term_months: int | None = None
    total_amount: Decimal | None = None
