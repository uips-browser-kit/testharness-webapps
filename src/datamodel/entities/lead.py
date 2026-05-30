from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel


class Lead(BaseModel):
    __business_key__: ClassVar[str] = "id"

    id: str
    first_name: str
    last_name: str
    company: str | None = None
    email: str | None = None
    phone: str | None = None
    status: str
    is_converted: bool
    converted_opportunity_id: str | None = None
