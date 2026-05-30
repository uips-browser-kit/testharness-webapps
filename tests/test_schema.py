from __future__ import annotations

from pathlib import Path

import pytest

from src.core.schema import EntitySchema, FieldDef, _parse_field, load_schema

_HARNESS_YAML = Path(__file__).parent.parent / "harness.yaml"


def test_filterable_defaults_to_false():
    fd = _parse_field({"type": "string", "nullable": False})
    assert fd.filterable is False


def test_filterable_parsed_true():
    fd = _parse_field({"type": "string", "nullable": False, "filterable": True})
    assert fd.filterable is True


def test_filterable_fields_method():
    es = EntitySchema(
        name="account",
        business_key="id",
        fields={
            "id": FieldDef(type="string", nullable=False, filterable=True),
            "name": FieldDef(type="string", nullable=False, filterable=True),
            "phone": FieldDef(type="string", nullable=True),
        },
        systems={},
    )
    assert es.filterable_fields() == ["id", "name"]


def test_load_schema_account_filterable_fields():
    schema = load_schema(_HARNESS_YAML)
    ff = schema["account"].filterable_fields()
    assert "id" in ff
    assert "name" in ff
    assert "owner" in ff
    assert "industry" not in ff
    assert "phone" not in ff
