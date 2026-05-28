import pytest
from pathlib import Path

from src.harness.data_loader import DataLoader, DataLoaderError

DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def loader():
    return DataLoader(DATA_DIR, "default")


def test_loads_without_error(loader):
    pass


def test_get_record_found(loader):
    record = loader.get_record("salesforce", "accounts", "id", "001")
    assert record is not None
    assert record["id"] == "001"


def test_get_record_not_found_returns_none(loader):
    assert loader.get_record("salesforce", "accounts", "id", "does-not-exist") is None


def test_get_all_returns_list(loader):
    records = loader.get_all("jira", "issues")
    assert isinstance(records, list)
    assert len(records) == 20


def test_get_all_unknown_entity_returns_empty(loader):
    assert loader.get_all("salesforce", "no_such_entity") == []


def test_missing_dataset_raises():
    with pytest.raises(DataLoaderError, match="Dataset directory not found"):
        DataLoader(DATA_DIR, "no-such-dataset")
