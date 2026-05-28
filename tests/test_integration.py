import yaml
import httpx
import pytest

from tests._integration_cases import all_route_cases
from tests.conftest import APPS_DIR

TIMEOUT = 5


# ---------------------------------------------------------------------------
# Health checks — one per app environment
# ---------------------------------------------------------------------------


def _health_cases():
    for path in sorted(APPS_DIR.glob("*/profile.yaml")):
        data = yaml.safe_load(path.read_text())["app"]
        app_id = data["id"]
        for env_id, env in data["environments"].items():
            yield pytest.param(app_id, env_id, env["host"], id=f"{app_id}/{env_id}")


@pytest.mark.integration
@pytest.mark.parametrize("app_id,env_id,host", list(_health_cases()))
def test_health_per_env(app_id, env_id, host):
    r = httpx.get(f"http://{host}/health", timeout=TIMEOUT)
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Route responses — data-driven URLs via catch-all + Caddy header echo
# ---------------------------------------------------------------------------


def _route_cases():
    for app_id, route_id, env_id, url in all_route_cases():
        suffix = url.split("/")[-1][:24]
        yield pytest.param(app_id, route_id, env_id, url, id=f"{app_id}/{route_id}/{env_id}/{suffix}")


@pytest.mark.integration
@pytest.mark.parametrize("app_id,route_id,env_id,url", list(_route_cases()))
def test_route_responds(app_id, route_id, env_id, url):
    r = httpx.get(url, timeout=TIMEOUT)
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    if "text/html" in ct:
        assert len(r.text) > 0, f"empty HTML body for {url}"
    else:
        body = r.json()
        assert body["app"] == app_id, f"expected app={app_id!r}, got {body['app']!r} ({url})"
        assert body["env"] == env_id, f"expected env={env_id!r}, got {body['env']!r} ({url})"
