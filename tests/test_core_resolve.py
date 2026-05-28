import pytest
import yaml

from src.core.models import NotServerVisible
from src.core.resolver import resolve
from tests.conftest import APPS_DIR, load_app


def _cases():
    for path in sorted(APPS_DIR.glob("*/resolve.yaml")):
        app_id = path.parent.name
        for case in yaml.safe_load(path.read_text())["cases"]:
            yield pytest.param(
                app_id,
                case,
                id=f"{app_id}/{case['route_id']}/{case['env_id']}",
            )


@pytest.mark.parametrize("app_id,case", list(_cases()))
def test_resolve(app_id, case):
    app = load_app(app_id)
    if "expected_error" in case:
        with pytest.raises(NotServerVisible):
            resolve(app, case["route_id"], case["env_id"], case.get("params", {}))
    else:
        result = resolve(app, case["route_id"], case["env_id"], case.get("params", {}))
        assert result == case["expected_url"]
