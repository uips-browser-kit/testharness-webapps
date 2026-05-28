from __future__ import annotations

from src.core.models import (
    App,
    DetailViewData,
    ListViewData,
    NotServerVisible,
    Route,
    RouteContext,
)
from src.core.resolver import resolve


def shape_detail(
    app: App, route: Route, ctx: RouteContext, raw: dict | None
) -> DetailViewData:
    return DetailViewData(
        entity_title=route.data_entity.replace("_", " ").title(),
        record=raw,
    )


def shape_list(
    app: App, route: Route, ctx: RouteContext, raw: list[dict]
) -> ListViewData:
    records = list(raw)

    if records and ctx.params:
        first = records[0]
        filter_keys = {k: v for k, v in ctx.params.items() if k in first}
        if filter_keys:
            records = [
                r for r in records
                if all(str(r.get(k)) == str(v) for k, v in filter_keys.items())
            ]

    detail_urls: dict[str, str] = {}
    detail_key_field = ""

    detail_route = next(
        (r for r in app.routes if r.data_entity == route.data_entity and r.data_key_field),
        None,
    )
    if detail_route and records:
        key_field = detail_route.data_key_field
        key_param = detail_route.data_key_param or key_field
        detail_key_field = key_field
        for rec in records:
            key_val = str(rec.get(key_field, ""))
            try:
                detail_urls[key_val] = resolve(
                    app,
                    detail_route.id,
                    ctx.env_id,
                    {**ctx.params, key_param: key_val},
                )
            except (NotServerVisible, KeyError, ValueError):
                pass

    return ListViewData(
        entity_title=route.data_entity.replace("_", " ").title(),
        records=records,
        detail_urls=detail_urls,
        detail_key_field=detail_key_field,
    )
