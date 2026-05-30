from __future__ import annotations

import json
from pathlib import Path

from src.backend.app_repository import _schema_name
from src.core.schema import EntitySchema


class DataLoaderError(Exception):
    pass


# Map from JSON file stem (entity name in data files) to schema entity name.
# Most stems are plural; this covers exceptions and non-obvious mappings.
_FILE_STEM_TO_SCHEMA: dict[str, str] = {
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


def _entity_schema_name(file_stem: str) -> str:
    return _FILE_STEM_TO_SCHEMA.get(file_stem, file_stem.rstrip("s"))


def _remap_record(record: dict, es: EntitySchema, app_id: str) -> dict:
    """Translate data-file field names to canonical model field names using schema alias."""
    mapping = es.systems.get(app_id)
    if not mapping or not mapping.alias:
        return record
    # alias: {data_file_field: canonical_model_field}
    return {mapping.alias.get(k, k): v for k, v in record.items()}


class DataLoader:
    """Loads data/{dataset}/{app_id}/*.json into memory at startup.

    Existing raw-dict interface (get_record, get_all, filter_by) is preserved
    for backward compatibility with tests and any remaining direct callers.

    The seed() method populates a CanonicalStore with typed domain objects.
    """

    def __init__(self, data_dir: Path, dataset: str = "default") -> None:
        dataset_dir = data_dir / dataset
        if not dataset_dir.is_dir():
            raise DataLoaderError(f"Dataset directory not found: {dataset_dir}")
        self._data: dict[str, dict[str, list[dict]]] = {}
        for app_dir in dataset_dir.iterdir():
            if app_dir.is_dir() and not app_dir.name.startswith("_"):
                self._data[app_dir.name] = {
                    f.stem: json.loads(f.read_text(encoding="utf-8"))
                    for f in sorted(app_dir.glob("*.json"))
                }

    # ------------------------------------------------------------------
    # Legacy raw-dict interface (preserved for backward compat)
    # ------------------------------------------------------------------

    def get_record(
        self, app_id: str, entity: str, key_field: str, key_value: str
    ) -> dict | None:
        records = self._data.get(app_id, {}).get(entity, [])
        return next((r for r in records if str(r.get(key_field)) == key_value), None)

    def get_all(self, app_id: str, entity: str) -> list[dict]:
        return self._data.get(app_id, {}).get(entity, [])

    def filter_by(self, app_id: str, entity: str, field: str, value: str) -> list[dict]:
        return [r for r in self.get_all(app_id, entity) if str(r.get(field)) == value]

    # ------------------------------------------------------------------
    # CanonicalStore seeding
    # ------------------------------------------------------------------

    def seed(
        self,
        store: object,  # CanonicalStore — typed as object to avoid circular import
        schema: dict[str, EntitySchema],
        shared_entities: dict[str, list[str]] | None = None,
    ) -> dict[str, int]:
        """Populate store with typed domain objects from all loaded data files.

        shared_entities maps entity data-file name → list[app_id] that share
        the same canonical records (e.g. accounts: [salesforce, dynamics]).
        Only the first app in the list is seeded for shared entities to avoid
        duplicates overwriting each other.

        Returns {entity_name: record_count} for successfully seeded entities.
        """
        from src.backend.app_repository import AppRepository  # noqa: PLC0415

        shared = shared_entities or {}
        # Build set of (app_id, file_stem) pairs that should be skipped
        # because another app is the canonical source for that entity.
        skip: set[tuple[str, str]] = set()
        for file_stem, app_ids in shared.items():
            for secondary in app_ids[1:]:
                skip.add((secondary, file_stem))

        repo = AppRepository(store, schema)  # type: ignore[arg-type]
        seeded: dict[str, int] = {}

        for app_id, entities in self._data.items():
            for file_stem, records in entities.items():
                if (app_id, file_stem) in skip:
                    continue
                entity_name = _entity_schema_name(file_stem)
                es = schema.get(entity_name)
                if es is None:
                    continue
                count = 0
                for raw in records:
                    remapped = _remap_record(raw, es, app_id)
                    obj = repo._validate(entity_name, remapped)
                    if obj is not None:
                        store.save(entity_name, obj)  # type: ignore[attr-defined]
                        count += 1
                if count:
                    seeded[entity_name] = seeded.get(entity_name, 0) + count

        return seeded
