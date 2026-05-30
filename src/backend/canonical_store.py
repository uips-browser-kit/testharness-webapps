from __future__ import annotations

from pydantic import BaseModel


class CanonicalStore:
    """In-memory store of domain objects keyed by (entity_name, business_key_value).

    Implements the CanonicalStore Protocol defined in src.datamodel.repositories.
    Entity names are the singular schema names (e.g. 'account', 'order').
    """

    def __init__(self) -> None:
        self._store: dict[str, dict[str, BaseModel]] = {}

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(self, entity: str, obj: BaseModel) -> None:
        """Store a domain object under its business key."""
        bk_field: str = getattr(type(obj), "__business_key__", "id")
        key = str(getattr(obj, bk_field, ""))
        if entity not in self._store:
            self._store[entity] = {}
        self._store[entity][key] = obj

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, entity: str, key: str) -> BaseModel | None:
        """Return the domain object with the given business key, or None."""
        return self._store.get(entity, {}).get(key)

    def find_by(self, entity: str, field: str, value: str) -> list[BaseModel]:
        """Return all objects of the given entity where field == value (string coercion)."""
        return [
            obj
            for obj in self._store.get(entity, {}).values()
            if str(getattr(obj, field, None)) == value
        ]

    def get_all(self, entity: str) -> list[BaseModel]:
        """Return all stored objects for an entity, in insertion order."""
        return list(self._store.get(entity, {}).values())

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def entity_names(self) -> list[str]:
        return list(self._store.keys())

    def count(self, entity: str) -> int:
        return len(self._store.get(entity, {}))
