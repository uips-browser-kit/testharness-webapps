from __future__ import annotations

from src.core.resolver import resolve
from tests.conftest import APPS_DIR, load_app, load_data

_SAMPLE = {
    "_adf.ctrl-state": "state-xyz",
    "workbook": "Sales",
    "view": "Overview",
    ":showVizHome": "no",
    "env_id": "env-001",
    "app_id": "app-001",
    "tenantId": "tenant-001",
    "screen": "Orders",
    "workspace": "my-workspace",
    "report_id": "rpt-001",
}

# app_id -> list of (route_id, data_file, field_map, fixed_params)
# field_map: {route_param: data_record_field}
_DATA_MAP: dict[str, list[tuple[str, str, dict[str, str], dict[str, str]]]] = {
    "salesforce": [
        ("account-detail", "accounts.json", {"id": "id"}, {}),
        ("contact-detail", "contacts.json", {"id": "id"}, {}),
        ("opportunity-detail", "opportunities.json", {"id": "id"}, {}),
    ],
    "dynamics": [
        (
            "account-detail",
            "accounts.json",
            {"id": "id"},
            {"appid": "app-001", "pagetype": "entityrecord"},
        )
    ],
    "servicenow": [("incident", "incidents.json", {"sys_id": "sys_id"}, {})],
    "sap": [("shell", "sales_orders.json", {"so": "order_number"}, {"sap-client": "100"})],
    "oracle": [
        (
            "invoice-detail",
            "invoices.json",
            {"invoice_number": "invoice_number"},
            {"_adf.ctrl-state": "state-xyz"},
        )
    ],
    "workday": [("task", "employees.json", {"id": "employee_id"}, {"redirect": "n"})],
    "jira": [("issue", "issues.json", {"issue_key": "key"}, {})],
    "confluence": [
        ("page", "pages.json", {"space_key": "space_key", "page_id": "page_id"}, {})
    ],
    "sharepoint": [("document-list", "documents.json", {"site_name": "site_name"}, {})],
    "power-bi": [
        (
            "report",
            "pipeline_by_stage.json",
            {},
            {"workspace": "my-workspace", "report_id": "rpt-001"},
        )
    ],
}


def all_route_cases() -> list[tuple[str, str, str, str]]:
    """Return (app_id, route_id, env_id, url) for every data record × every env."""
    cases: list[tuple[str, str, str, str]] = []

    for app_dir in sorted(APPS_DIR.iterdir()):
        if not app_dir.is_dir():
            continue
        app_id = app_dir.name
        app = load_app(app_id)

        # Data-driven routes
        for route_id, filename, field_map, fixed in _DATA_MAP.get(app_id, []):
            records = load_data(app_id, filename)
            seen: set[tuple] = set()
            for record in records:
                params = {**fixed}
                if app_id == "power-bi" and "region" in record:
                    params["filter"] = f"Region eq '{record['region']}'"
                for route_param, data_field in field_map.items():
                    params[route_param] = str(record[data_field])
                key = tuple(sorted(params.items()))
                if key in seen:
                    continue
                seen.add(key)
                for env_id in app.environments:
                    cases.append((app_id, route_id, env_id, resolve(app, route_id, env_id, params)))

        # SAMPLE_PARAMS fallback for apps with no data mapping (oracle, tableau, power-apps)
        if app_id not in _DATA_MAP:
            for route in app.routes:
                if not route.server_visible:
                    continue
                for env_id in app.environments:
                    cases.append(
                        (app_id, route.id, env_id, resolve(app, route.id, env_id, _SAMPLE))
                    )

        # Param-free routes (salesforce/dashboard, workday/home) — 1 URL per env
        for route in app.routes:
            if route.query_params or "{" in route.path or not route.server_visible:
                continue
            for env_id in app.environments:
                cases.append((app_id, route.id, env_id, resolve(app, route.id, env_id, {})))

    return cases
