from __future__ import annotations

from datetime import date
from typing import ClassVar

from pydantic import BaseModel


class Page(BaseModel):
    __business_key__: ClassVar[str] = "page_id"

    page_id: str
    title: str
    space_key: str
    author: str | None = None
    last_modified: date | None = None
    created_date: date | None = None
    labels: list[str] = []
    excerpt: str | None = None
