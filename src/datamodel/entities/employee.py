from __future__ import annotations

from datetime import date
from typing import ClassVar

from pydantic import BaseModel


class Employee(BaseModel):
    __business_key__: ClassVar[str] = "employee_id"

    employee_id: str
    first_name: str
    last_name: str
    job_title: str | None = None
    department: str | None = None
    manager: str | None = None
    email: str | None = None
    hire_date: date | None = None
    location: str | None = None
