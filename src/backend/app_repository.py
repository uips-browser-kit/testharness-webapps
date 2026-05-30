from __future__ import annotations

from pydantic import BaseModel

from src.backend.canonical_store import CanonicalStore
from src.core.schema import EntitySchema


# Map from data_entity name (as used in routes/data files) to schema entity name (singular).
# Covers cases where they differ; others are handled by stripping a trailing 's'.
_DATA_ENTITY_TO_SCHEMA: dict[str, str] = {
    "sales_orders": "order",
    "order_items": "order_item",
    "opportunities": "opportunity",
    "accounts": "account",
    "contacts": "contact",
    "invoices": "invoice",
    "incidents": "incident",
    "employees": "employee",
    "products": "product",
    "contracts": "contract",
    "cases": "case",
    "leads": "lead",
    "pages": "page",
    "issues": "issue",
    "documents": "document",
}


def _schema_name(data_entity: str) -> str:
    return _DATA_ENTITY_TO_SCHEMA.get(data_entity, data_entity.rstrip("s"))


class AppRepository:
    """Schema-driven bidirectional adapter between app dialect and CanonicalStore.

    Read path  (canonical → app):
        fetch domain object from store → apply SystemMapping.alias forward →
        return dict with app-specific field names.

    Write path (app → canonical):
        apply reverse alias (app field → canonical field) →
        Model.model_validate() → save to store.
    """

    def __init__(
        self,
        store: CanonicalStore,
        schema: dict[str, EntitySchema],
    ) -> None:
        self._store = store
        self._schema = schema

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, app_id: str, data_entity: str, key: str) -> dict | None:
        """Return a dict in the app's field dialect for the given business key."""
        entity_name = _schema_name(data_entity)
        obj = self._store.get(entity_name, key)
        if obj is None:
            return None
        return self._to_app_dict(app_id, entity_name, obj)

    def find(self, app_id: str, data_entity: str) -> list[dict]:
        """Return all records for an entity in the app's field dialect."""
        entity_name = _schema_name(data_entity)
        return [
            self._to_app_dict(app_id, entity_name, obj)
            for obj in self._store.get_all(entity_name)
        ]

    def find_by(self, app_id: str, data_entity: str, field: str, value: str) -> list[dict]:
        """Return records where canonical field == value, in the app's dialect.

        `field` is the app-dialect field name; it is translated to canonical
        before the store lookup.
        """
        entity_name = _schema_name(data_entity)
        es = self._schema.get(entity_name)
        canonical_f = es.canonical_field(app_id, field) if es else field
        return [
            self._to_app_dict(app_id, entity_name, obj)
            for obj in self._store.find_by(entity_name, canonical_f, value)
        ]

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(self, app_id: str, data_entity: str, data: dict) -> None:
        """Translate app-dialect dict to canonical, validate, and store."""
        entity_name = _schema_name(data_entity)
        es = self._schema.get(entity_name)
        canonical_data = self._to_canonical_dict(app_id, entity_name, data, es)
        model_cls = self._store.get(entity_name, "_model_cls_sentinel")
        # Build the domain object; requires the entity class to be retrievable.
        # We find it via the store's existing objects or fall back to raw dict storage.
        obj = self._validate(entity_name, canonical_data)
        if obj is not None:
            self._store.save(entity_name, obj)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _to_app_dict(self, app_id: str, entity_name: str, obj: BaseModel) -> dict:
        """Convert a domain object to an app-dialect dict.

        alias: {system_field: canonical_field}
        To go canonical → system: invert to {canonical_field: system_field}.
        """
        raw = obj.model_dump()
        es = self._schema.get(entity_name)
        if not es:
            return raw
        mapping = es.systems.get(app_id)
        if not mapping or not mapping.alias:
            return raw
        # build canonical→system map once
        canonical_to_system = {cv: sk for sk, cv in mapping.alias.items()}
        return {canonical_to_system.get(k, k): v for k, v in raw.items()}

    def _to_canonical_dict(
        self,
        app_id: str,
        entity_name: str,
        data: dict,
        es: EntitySchema | None,
    ) -> dict:
        """Translate app-dialect dict fields to canonical field names."""
        if not es:
            return data
        mapping = es.systems.get(app_id)
        if not mapping or not mapping.alias:
            return data
        # alias: {system_field: canonical_field} — direct lookup gives canonical name
        return {mapping.alias.get(k, k): v for k, v in data.items()}

    def _validate(self, entity_name: str, data: dict) -> BaseModel | None:
        """Construct a domain object from canonical dict data."""
        from src.datamodel.entities import (  # noqa: PLC0415
            Account, Case, Contact, Contract, Document, Employee,
            Incident, Invoice, JiraIssue, Lead, Order, OrderItem,
            Opportunity, Page, Product,
        )
        _CLASSES: dict[str, type[BaseModel]] = {
            "account": Account, "contact": Contact, "opportunity": Opportunity,
            "case": Case, "lead": Lead, "order": Order, "order_item": OrderItem,
            "product": Product, "contract": Contract, "invoice": Invoice,
            "incident": Incident, "employee": Employee, "page": Page,
            "issue": JiraIssue, "document": Document,
        }
        cls = _CLASSES.get(entity_name)
        if cls is None:
            return None
        try:
            return cls.model_validate(data)
        except Exception:
            return None
