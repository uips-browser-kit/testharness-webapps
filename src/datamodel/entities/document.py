from __future__ import annotations

from datetime import date
from typing import ClassVar

from pydantic import BaseModel


class Document(BaseModel):
    __business_key__: ClassVar[str] = "id"

    id: str
    filename: str
    library: str | None = None
    author: str | None = None
    modified_date: date | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    site_name: str | None = None
