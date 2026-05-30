from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


class SchemaError(Exception):
    pass


@dataclass
class FieldDef:
    type: str           # string | integer | decimal | date | object | boolean
    nullable: bool
    ref: str = ""       # "entity.field" — FK target in canonical entity terms


@dataclass
class SystemMapping:
    pk: str                                    # PK field name in this system's data files
    alias: dict[str, str] = field(default_factory=dict)  # canonical_field -> system_field


@dataclass
class EntitySchema:
    name: str
    business_key: str
    fields: dict[str, FieldDef]
    systems: dict[str, SystemMapping]

    def pk_for(self, app_id: str) -> str:
        """Return the PK field name as used by this app's data files."""
        mapping = self.systems.get(app_id)
        return mapping.pk if mapping else self.business_key

    def refs(self) -> list[tuple[str, str]]:
        """Return [(field_name, 'target_entity.target_field'), ...] for FK fields."""
        return [(name, f.ref) for name, f in self.fields.items() if f.ref]

    def canonical_field(self, app_id: str, app_field: str) -> str:
        """Translate an app-specific (data file) field name to the canonical field name.

        The alias dict stores {system_field: canonical_field}, so a direct lookup
        gives the canonical name for a given system field name.
        """
        mapping = self.systems.get(app_id)
        if not mapping or not mapping.alias:
            return app_field
        return mapping.alias.get(app_field, app_field)

    def app_field(self, app_id: str, canonical_field_name: str) -> str:
        """Translate a canonical field name to the app-specific (data file) field name.

        Inverts the alias dict ({system_field: canonical_field}) to find the
        system field name for a given canonical field name.
        """
        mapping = self.systems.get(app_id)
        if not mapping or not mapping.alias:
            return canonical_field_name
        inverse = {v: k for k, v in mapping.alias.items()}
        return inverse.get(canonical_field_name, canonical_field_name)


def _parse_field(raw: dict) -> FieldDef:
    return FieldDef(
        type=str(raw.get("type", "string")),
        nullable=bool(raw.get("nullable", True)),
        ref=str(raw.get("ref", "")),
    )


def _parse_system(raw: dict) -> SystemMapping:
    return SystemMapping(
        pk=str(raw.get("pk", "id")),
        alias=dict(raw.get("alias", {})),
    )


def load_schema(path: Path) -> dict[str, EntitySchema]:
    """Parse the active dataset's schema from harness.yaml.

    Returns a dict keyed by singular entity name (e.g. 'account', 'order').
    Returns an empty dict when no schema is defined for the active dataset.
    """
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    data_raw = raw.get("data", {})
    if not isinstance(data_raw, dict):
        return {}

    set_name = str(data_raw.get("set", "default"))
    dataset = data_raw.get("datasets", {}).get(set_name, {})
    schema_entities = dataset.get("schema", {}).get("entities", {})

    result: dict[str, EntitySchema] = {}
    for entity_name, entity_raw in schema_entities.items():
        if not isinstance(entity_raw, dict):
            raise SchemaError(f"Entity {entity_name!r} must be a mapping")
        business_key = entity_raw.get("business_key")
        if not business_key:
            raise SchemaError(f"Entity {entity_name!r} missing 'business_key'")

        fields = {
            fname: _parse_field(fdef if isinstance(fdef, dict) else {})
            for fname, fdef in entity_raw.get("fields", {}).items()
        }
        systems = {
            sname: _parse_system(sdef if isinstance(sdef, dict) else {})
            for sname, sdef in entity_raw.get("systems", {}).items()
        }
        result[entity_name] = EntitySchema(
            name=entity_name,
            business_key=str(business_key),
            fields=fields,
            systems=systems,
        )

    return result
