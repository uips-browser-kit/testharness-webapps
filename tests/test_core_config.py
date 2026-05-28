import pytest
from pathlib import Path

from src.core.config import ConfigError, load_config

CONFIGS = Path(__file__).parent / "fixtures" / "configs"


@pytest.mark.parametrize("path", sorted((CONFIGS / "valid").glob("*.yaml")))
def test_valid_config_loads(path):
    apps = load_config(path)
    assert len(apps) > 0


@pytest.mark.parametrize("path", sorted((CONFIGS / "invalid").glob("*.yaml")))
def test_invalid_config_raises(path):
    with pytest.raises(ConfigError):
        load_config(path)
