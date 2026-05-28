from urllib.parse import parse_qs, urlparse

import pytest
import yaml

from src.core.matcher import match
from tests.conftest import APPS_DIR, load_all_apps

_ALL_APPS = None


def _get_apps():
    global _ALL_APPS
    if _ALL_APPS is None:
        _ALL_APPS = load_all_apps()
    return _ALL_APPS


def _cases():
    for path in sorted(APPS_DIR.glob("*/match.yaml")):
        app_id = path.parent.name
        for case in yaml.safe_load(path.read_text())["cases"]:
            yield pytest.param(case, id=f"{app_id}/{case['url']}")


@pytest.mark.parametrize("case", list(_cases()))
def test_match(case):
    parsed = urlparse(case["url"])
    query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    result = match(host=parsed.hostname, path=parsed.path, query=query, apps=_get_apps())
    assert result is not None
    assert result.app_id == case["expected_app"]
    assert result.route_id == case["expected_route"]
    assert result.env_id == case["expected_env"]
    assert result.params == case["expected_params"]
