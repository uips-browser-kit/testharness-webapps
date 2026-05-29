from __future__ import annotations

from src.backend.data_loader import DataLoader
from src.core.models import (
    App,
    DetailViewData,
    ListViewData,
    NotServerVisible,
    RelatedPanel,
    Route,
    RouteContext,
)
from src.core.resolver import resolve


def shape_detail(
    app: App,
    route: Route,
    ctx: RouteContext,
    raw: dict | None,
    loader: DataLoader | None = None,
) -> DetailViewData:
    entity_title = route.data_entity.replace("_", " ").title()
    list_url = ""
    list_route = next(
        (r for r in app.routes if r.data_entity == route.data_entity and not r.data_key_field and r.id != route.id),
        None,
    )
    if list_route:
        key_param_name = route.data_key_param or route.data_key_field
        list_params = {k: v for k, v in ctx.params.items() if k != key_param_name}
        try:
            list_url = resolve(app, list_route.id, ctx.env_id, list_params)
        except (NotServerVisible, KeyError, ValueError):
            pass

    panels: list[RelatedPanel] = []
    if raw and loader and route.related:
        pk_value = str(raw.get(route.data_key_field, ""))
        for rel in route.related:
            if rel.via:
                rel_records: list[dict] = loader.filter_by(ctx.app_id, rel.entity, rel.via, pk_value)
            elif rel.from_field:
                fk_value = str(raw.get(rel.from_field, ""))
                parent = loader.get_record(ctx.app_id, rel.entity, "id", fk_value)
                rel_records = [parent] if parent else []
            else:
                continue
            if rel.fields:
                rel_records = [{f: r.get(f) for f in rel.fields} for r in rel_records]
            panels.append(RelatedPanel(
                entity_title=rel.entity.replace("_", " ").title(),
                records=rel_records,
                fields=rel.fields,
            ))

    return DetailViewData(
        entity_title=entity_title,
        record=raw,
        list_url=list_url,
        related_panels=panels,
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
    row_urls: list[str] = []

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
            url = ""
            try:
                url = resolve(
                    app,
                    detail_route.id,
                    ctx.env_id,
                    {**ctx.params, key_param: key_val},
                )
                detail_urls[key_val] = url
            except (NotServerVisible, KeyError, ValueError):
                pass
            row_urls.append(url)

    # Project to summary fields AFTER building URLs so key_field remains accessible
    if route.list_fields and records:
        records = [{f: r.get(f) for f in route.list_fields} for r in records]

    return ListViewData(
        entity_title=route.data_entity.replace("_", " ").title(),
        records=records,
        detail_urls=detail_urls,
        detail_key_field=detail_key_field,
        row_urls=row_urls,
    )
