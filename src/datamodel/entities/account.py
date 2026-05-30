from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

from pydantic import BaseModel


class Account(BaseModel):
    __business_key__: ClassVar[str] = "id"

    id: str
    name: str
    industry: str | None = None
    phone: str | None = None
    annual_revenue: Decimal | None = None
    website: str | None = None
    billing_address: dict | None = None
    owner: str | None = None
