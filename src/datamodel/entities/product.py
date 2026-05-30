from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

from pydantic import BaseModel


class Product(BaseModel):
    __business_key__: ClassVar[str] = "material_number"

    material_number: str
    description: str
    unit: str
    price: Decimal
    currency: str
    category: str | None = None
