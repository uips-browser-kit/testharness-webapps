from __future__ import annotations

from pathlib import Path

import pytest

from src.core.schema import CollectionDef, EntitySchema, FieldDef, _parse_collection, _parse_field, load_schema

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


def test_collection_parsed():
    cd = _parse_collection({"entity": "order_item", "via": "order_number"})
    assert cd.entity == "order_item"
    assert cd.via == "order_number"
    assert cd.fields == []


def test_collection_parsed_with_fields():
    cd = _parse_collection({"entity": "order_item", "via": "order_number", "fields": ["quantity", "price_per_unit"]})
    assert cd.fields == ["quantity", "price_per_unit"]


def test_load_schema_order_has_line_items_collection():
    schema = load_schema(_HARNESS_YAML)
    coll = schema["order"].collections
    assert "line_items" in coll
    assert coll["line_items"].entity == "order_item"
    assert coll["line_items"].via == "order_number"
    assert "material_number" in coll["line_items"].fields


def test_account_has_no_collections():
    schema = load_schema(_HARNESS_YAML)
    assert schema["account"].collections == {}


def test_display_field_defaults_to_name():
    schema = load_schema(_HARNESS_YAML)
    assert schema["account"].display_field == "name"
    assert schema["opportunity"].display_field == "name"


def test_display_field_custom():
    schema = load_schema(_HARNESS_YAML)
    assert schema["product"].display_field == "description"
    assert schema["incident"].display_field == "short_description"
    assert schema["page"].display_field == "title"
