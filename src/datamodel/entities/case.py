from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel


class Case(BaseModel):
    __business_key__: ClassVar[str] = "id"

    id: str
    account_id: str
    contact_id: str | None = None
    subject: str
    status: str
    priority: str
    type: str | None = None
    origin: str | None = None
