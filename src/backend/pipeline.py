from __future__ import annotations

from src.backend.data_loader import DataLoader
from src.backend.shaper import shape_detail, shape_list
from src.core.models import App, Route, RouteContext, ViewData


def prepare_view(
    app: App, route: Route, ctx: RouteContext, loader: DataLoader
) -> ViewData | None:
    """Load and shape view data for a route. Returns None for template-only routes."""
    if not route.data_entity:
        return None
    if route.data_key_field:
        param_name = route.data_key_param or route.data_key_field
        key_value = ctx.params.get(param_name, "")
        raw = loader.get_record(ctx.app_id, route.data_entity, route.data_key_field, key_value)
        return shape_detail(app, route, ctx, raw, loader)
    else:
        raw_list = loader.get_all(ctx.app_id, route.data_entity)
        return shape_list(app, route, ctx, raw_list)
