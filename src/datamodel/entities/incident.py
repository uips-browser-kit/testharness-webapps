from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel


class Incident(BaseModel):
    __business_key__: ClassVar[str] = "number"

    sys_id: str
    number: str
    account_id: str
    contact_id: str | None = None
    short_description: str
    state: str
    priority: int  # ServiceNow stores priority as integer (1=Critical … 5=Planning)
    category: str | None = None
    origin: str | None = None
