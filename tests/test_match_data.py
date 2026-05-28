from urllib.parse import parse_qs, urlparse

import pytest

from src.core.matcher import match
from tests._integration_cases import all_route_cases
from tests.conftest import load_all_apps

_APPS = None


def _get_apps():
    global _APPS
    if _APPS is None:
        _APPS = load_all_apps()
    return _APPS


def _cases():
    for app_id, route_id, env_id, url in all_route_cases():
        suffix = url.split("/")[-1][:24]
        yield pytest.param(app_id, route_id, env_id, url, id=f"{app_id}/{route_id}/{env_id}/{suffix}")


@pytest.mark.parametrize("app_id,route_id,env_id,url", list(_cases()))
def test_match_data(app_id, route_id, env_id, url):
    parsed = urlparse(url)
    query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    result = match(host=parsed.hostname, path=parsed.path, query=query, apps=_get_apps())
    assert result is not None, f"No match for {url}"
    assert result.app_id == app_id
    assert result.route_id == route_id
    assert result.env_id == env_id
