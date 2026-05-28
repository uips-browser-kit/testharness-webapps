"""
Spike: enterprise app URL patterns expressed as code.

Part A — generic examples, one per PatternType
Part B — 12 catalog apps from docs/app-profile-catalog.md

Run:
    uv run python scripts/catalog_urls.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlencode


# ---------------------------------------------------------------------------
# Core types
# ---------------------------------------------------------------------------


class PatternType(Enum):
    PATH = "path"           # /resource/{id}          — path substitution
    QUERY_ONLY = "query"    # /page?id={id}            — static path, params in query
    HASH = "hash"           # /#/resource/{id}         — NOT server-visible
    PROTOCOL = "protocol"   # myapp://open/123         — NOT server-visible


class NotServerVisible(Exception):
    pass


@dataclass
class Environment:
    host: str
    base_path: str = "/"


@dataclass
class Route:
    id: str
    path: str
    pattern_type: PatternType
    query_params: list[str] = field(default_factory=list)
    server_visible: bool = True
    note: str = ""


@dataclass
class App:
    id: str
    vendor: str
    product: str
    environments: dict[str, Environment]
    routes: list[Route]

    def route(self, route_id: str) -> Route:
        for r in self.routes:
            if r.id == route_id:
                return r
        raise KeyError(f"Route {route_id!r} not found in app {self.id!r}")

    def resolve(
        self,
        route_id: str,
        environment: str,
        params: dict[str, str] | None = None,
    ) -> str:
        params = params or {}
        env = self.environments[environment]
        r = self.route(route_id)

        if not r.server_visible:
            raise NotServerVisible(
                f"{self.id}.{route_id} uses {r.pattern_type.value} "
                f"routing — not visible to the server"
            )

        base = env.base_path.rstrip("/")
        path = r.path
        query: dict[str, str] = {}

        if r.pattern_type == PatternType.PATH:
            for name in re.findall(r"\{(\w+)\}", path):
                if name in params:
                    path = path.replace(f"{{{name}}}", params[name])
            for qp in r.query_params:
                if qp in params:
                    query[qp] = params[qp]

        elif r.pattern_type == PatternType.QUERY_ONLY:
            for qp in r.query_params:
                if qp in params:
                    query[qp] = params[qp]

        url = f"http://{env.host}{base}{path}"
        if query:
            url += "?" + urlencode(query)
        return url


# ---------------------------------------------------------------------------
# Part A — generic pattern examples
# ---------------------------------------------------------------------------

EXAMPLE_PATH = App(
    id="example-path",
    vendor="Example",
    product="REST-style App",
    environments={"default": Environment("app.company.com")},
    routes=[
        Route("resource", "/products/{id}", PatternType.PATH),
    ],
)

EXAMPLE_QUERY_ONLY = App(
    id="example-query",
    vendor="Example",
    product="Legacy Web App",
    environments={"default": Environment("app.company.com")},
    routes=[
        Route("order", "/orders", PatternType.QUERY_ONLY, query_params=["page", "id"]),
    ],
)

EXAMPLE_HASH = App(
    id="example-hash",
    vendor="Example",
    product="Older SPA",
    environments={"default": Environment("app.company.com")},
    routes=[
        Route(
            "order",
            "/#/orders/{id}",
            PatternType.HASH,
            server_visible=False,
            note="Hash fragment not sent to server",
        ),
    ],
)

EXAMPLE_PROTOCOL = App(
    id="example-protocol",
    vendor="Example",
    product="Desktop App",
    environments={"default": Environment("myapp")},
    routes=[
        Route(
            "open",
            "://open/{id}",
            PatternType.PROTOCOL,
            server_visible=False,
            note="Custom protocol — OS-handled, not HTTP",
        ),
    ],
)

GENERIC_EXAMPLES: list[App] = [
    EXAMPLE_PATH,
    EXAMPLE_QUERY_ONLY,
    EXAMPLE_HASH,
    EXAMPLE_PROTOCOL,
]


# ---------------------------------------------------------------------------
# Part B — catalog apps
# ---------------------------------------------------------------------------

SALESFORCE = App(
    id="salesforce",
    vendor="Salesforce",
    product="Lightning",
    environments={
        "dev":  Environment("sf-dev.local"),
        "prod": Environment("salesforce.company.com"),
    },
    routes=[
        Route("account-detail", "/lightning/r/Account/{id}/view", PatternType.PATH),
        Route("dashboard",      "/lightning/page/home",           PatternType.PATH),
    ],
)

DYNAMICS = App(
    id="dynamics",
    vendor="Microsoft",
    product="Dynamics 365",
    environments={
        "dev":  Environment("org.crm.dynamics.com"),
        "prod": Environment("dynamics.company.com"),
    },
    routes=[
        Route(
            "record",
            "/main.aspx",
            PatternType.QUERY_ONLY,
            query_params=["appid", "pagetype", "id"],
        ),
    ],
)

SERVICENOW = App(
    id="servicenow",
    vendor="ServiceNow",
    product="Workspace",
    environments={
        "dev":  Environment("instance.service-now.com"),
        "prod": Environment("servicedesk.company.com"),
    },
    routes=[
        Route(
            "incident",
            "/now/workspace/agent/record/incident/{sys_id}",
            PatternType.PATH,
        ),
    ],
)

SAP = App(
    id="sap",
    vendor="SAP",
    product="Fiori",
    environments={
        "dev":  Environment("erp-dev.company.com"),
        "prod": Environment("erp.company.com"),
    },
    routes=[
        Route(
            "shell",
            "/sap/bc/ui5_ui5/ui2/ushell",
            PatternType.QUERY_ONLY,
            query_params=["sap-client", "so"],
            note="Hash fragment (#SalesOrder-display?SO=...) is not server-visible; "
                 "'so' is the harness server-side representation",
        ),
    ],
)

ORACLE = App(
    id="oracle",
    vendor="Oracle",
    product="Fusion / EBS",
    environments={
        "dev":  Environment("oracle-dev.company.com"),
        "prod": Environment("finance.company.com"),
    },
    routes=[
        Route(
            "welcome",
            "/fscmUI/faces/FuseWelcome",
            PatternType.QUERY_ONLY,
            query_params=["_adf.ctrl-state"],
        ),
    ],
)

WORKDAY = App(
    id="workday",
    vendor="Workday",
    product="Workday",
    environments={
        "dev":  Environment("tenant.workday.com"),
        "prod": Environment("hr.company.com"),
    },
    routes=[
        Route("home", "/home",       PatternType.PATH),
        Route("task", "/home.htmld", PatternType.QUERY_ONLY, query_params=["redirect", "id"]),
    ],
)

JIRA = App(
    id="jira",
    vendor="Atlassian",
    product="Jira",
    environments={
        "cloud":       Environment("jira.company.atlassian.net"),
        "self-hosted": Environment("jira.company.com"),
    },
    routes=[
        Route("issue", "/browse/{issue_key}", PatternType.PATH),
    ],
)

CONFLUENCE = App(
    id="confluence",
    vendor="Atlassian",
    product="Confluence",
    environments={
        "cloud":       Environment("confluence.company.atlassian.net", base_path="/wiki"),
        "self-hosted": Environment("wiki.company.com"),
    },
    routes=[
        Route("page", "/spaces/{space_key}/pages/{page_id}", PatternType.PATH),
    ],
)

SHAREPOINT = App(
    id="sharepoint",
    vendor="Microsoft",
    product="SharePoint",
    environments={
        "cloud":       Environment("tenant.sharepoint.com"),
        "self-hosted": Environment("intranet.company.com"),
    },
    routes=[
        Route(
            "documents",
            "/sites/{site_name}/Shared%20Documents/Forms/AllItems.aspx",
            PatternType.PATH,
            note="URL-encoded space is a static segment — preserved as-is",
        ),
    ],
)

POWER_BI = App(
    id="power-bi",
    vendor="Microsoft",
    product="Power BI",
    environments={
        "cloud":       Environment("app.powerbi.com"),
        "self-hosted": Environment("analytics.company.com"),
    },
    routes=[
        Route(
            "report",
            "/groups/{workspace}/reports/{report_id}",
            PatternType.PATH,
            query_params=["filter"],
        ),
    ],
)

TABLEAU = App(
    id="tableau",
    vendor="Tableau",
    product="Tableau Server",
    environments={
        "cloud":       Environment("server.tableau.com"),
        "self-hosted": Environment("tableau.company.com"),
    },
    routes=[
        Route(
            "view",
            "/views/{workbook}/{view}",
            PatternType.PATH,
            query_params=[":showVizHome"],
            note="Tableau colon-prefixed params are treated as regular query params; "
                 "urlencode will percent-encode the colon",
        ),
    ],
)

POWER_APPS = App(
    id="power-apps",
    vendor="Microsoft",
    product="Power Apps",
    environments={
        "cloud":       Environment("apps.powerapps.com"),
        "self-hosted": Environment("apps.company.com"),
    },
    routes=[
        Route(
            "app",
            "/play/e/{env_id}/a/{app_id}",
            PatternType.PATH,
            query_params=["tenantId", "screen"],
        ),
    ],
)

CATALOG_APPS: list[App] = [
    SALESFORCE, DYNAMICS, SERVICENOW, SAP, ORACLE, WORKDAY,
    JIRA, CONFLUENCE, SHAREPOINT, POWER_BI, TABLEAU, POWER_APPS,
]

# ---------------------------------------------------------------------------
# Sample params
# ---------------------------------------------------------------------------

SAMPLE_PARAMS: dict[str, str] = {
    "id":               "001",
    "sys_id":           "abc123def456",
    "issue_key":        "ABC-123",
    "space_key":        "ENG",
    "page_id":          "98765",
    "site_name":        "HR",
    "workspace":        "my-workspace",
    "report_id":        "rpt-001",
    "workbook":         "Sales",
    "view":             "Overview",
    "env_id":           "env-001",
    "app_id":           "app-001",
    "appid":            "app-001",
    "pagetype":         "entityrecord",
    "sap-client":       "100",
    "so":               "12345",
    "_adf.ctrl-state":  "state-xyz",
    "redirect":         "n",
    "filter":           "Region eq 'EMEA'",
    ":showVizHome":     "no",
    "tenantId":         "tenant-001",
    "screen":           "Orders",
    "page":             "1",
}


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def print_app(app: App, params: dict[str, str]) -> None:
    print(f"\n{'─' * 72}")
    print(f"  {app.vendor} — {app.product}  [{app.id}]")
    print(f"{'─' * 72}")
    for route in app.routes:
        if route.note:
            print(f"  note  {route.note}")
        for env_id, _ in app.environments.items():
            label = f"{route.id} [{env_id}]"
            try:
                url = app.resolve(route.id, env_id, params)
                print(f"  {label:<38}  {url}")
            except NotServerVisible as exc:
                print(f"  {label:<38}  [NOT SERVER-VISIBLE]  ({exc})")


if __name__ == "__main__":
    print("=" * 72)
    print("  PART A — Generic pattern examples")
    print("=" * 72)
    for app in GENERIC_EXAMPLES:
        print_app(app, SAMPLE_PARAMS)

    print()
    print("=" * 72)
    print("  PART B — Catalog apps")
    print("=" * 72)
    for app in CATALOG_APPS:
        print_app(app, SAMPLE_PARAMS)

    print()
