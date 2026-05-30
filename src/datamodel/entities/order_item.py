from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

from pydantic import BaseModel


class OrderItem(BaseModel):
    """Canonical field names differ from some data files:
    - canonical/order_items.json uses order_id (→ order_number), product_id (→ material_number),
      unit_price (→ price_per_unit); DataLoader remaps on load.
    """

    __business_key__: ClassVar[str] = "id"

    id: str
    order_number: str
    material_number: str
    quantity: int
    price_per_unit: Decimal
    total_price: Decimal
