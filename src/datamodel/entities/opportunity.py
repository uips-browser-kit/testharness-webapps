from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import ClassVar

from pydantic import BaseModel


class Opportunity(BaseModel):
    __business_key__: ClassVar[str] = "id"

    id: str
    name: str
    account_id: str
    amount: Decimal
    stage: str
    close_date: date
    owner: str | None = None
