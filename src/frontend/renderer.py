from pathlib import Path

from fastapi import HTTPException
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from src.core.models import App, RouteContext

_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"

_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=True,
)


def render(app: App, template_name: str, ctx: RouteContext, extra: dict | None = None) -> str:
    """Render a Jinja2 template and return HTML.

    Template resolution:
      - "shared/list"   → templates/shared/list.html   (cross-app generic)
      - "account_list"  → templates/{app.id}/account_list.html  (per-app)
    """
    if "/" in template_name:
        path = f"{template_name}.html"
    else:
        path = f"{app.id}/{template_name}.html"
    try:
        template = _jinja_env.get_template(path)
    except TemplateNotFound:
        raise HTTPException(status_code=500, detail=f"Template not found: {path}")

    context = {
        "app_id": app.id,
        "app_name": app.product,
        "env_name": ctx.env_id,
        "layout": app.layout,
        "nav_items": app.nav,
        "current_route_id": ctx.route_id,
        "params": ctx.params,
        **(extra or {}),
    }
    return template.render(**context)
