import json
from pathlib import Path


class DataLoaderError(Exception):
    pass


class DataLoader:
    """Loads data/{dataset}/{app_id}/*.json into memory at startup."""

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

    def get_record(
        self, app_id: str, entity: str, key_field: str, key_value: str
    ) -> dict | None:
        records = self._data.get(app_id, {}).get(entity, [])
        return next((r for r in records if str(r.get(key_field)) == key_value), None)

    def get_all(self, app_id: str, entity: str) -> list[dict]:
        return self._data.get(app_id, {}).get(entity, [])

    def filter_by(self, app_id: str, entity: str, field: str, value: str) -> list[dict]:
        return [r for r in self.get_all(app_id, entity) if str(r.get(field)) == value]
