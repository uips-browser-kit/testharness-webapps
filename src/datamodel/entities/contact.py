from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel


class Contact(BaseModel):
    __business_key__: ClassVar[str] = "id"

    id: str
    account_id: str
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    title: str | None = None
