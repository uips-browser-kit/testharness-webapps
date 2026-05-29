import json
from pathlib import Path

import yaml

from src.core.config import parse_data_set
from src.core.models import App, Environment, PatternType, Route

_HARNESS_YAML = Path(__file__).parent.parent / "harness.yaml"
APPS_DIR = Path(__file__).parent / "fixtures" / "apps"
DATA_DIR = Path(__file__).parent.parent / "data" / parse_data_set(_HARNESS_YAML)


def load_app(app_id: str) -> App:
    data = yaml.safe_load((APPS_DIR / app_id / "profile.yaml").read_text())["app"]
    return App(
        id=data["id"],
        vendor=data["vendor"],
        product=data["product"],
        environments={
            k: Environment(host=v["host"], base_path=v["base_path"])
            for k, v in data["environments"].items()
        },
        routes=[
            Route(
                id=r["id"],
                path=r["path"],
                pattern_type=PatternType(r["pattern_type"]),
                query_params=r.get("query_params", []),
                server_visible=r.get("server_visible", True),
                note=r.get("note", ""),
            )
            for r in data["routes"]
        ],
    )


def load_all_apps() -> list[App]:
    return [load_app(p.name) for p in sorted(APPS_DIR.iterdir()) if p.is_dir()]


def load_data(app_id: str, filename: str) -> list[dict]:
    return json.loads((DATA_DIR / app_id / filename).read_text())
