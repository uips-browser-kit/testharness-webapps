from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel


class JiraIssue(BaseModel):
    __business_key__: ClassVar[str] = "key"

    key: str
    summary: str
    issue_type: str
    status: str
    priority: str | None = None
    assignee: str | None = None
    reporter: str | None = None
    description: str | None = None
    created: datetime | None = None
    updated: datetime | None = None
    labels: list[str] = []
    sprint: str | None = None
