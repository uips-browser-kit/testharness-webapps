# Extension (Plugin) Specification — v1

## Status

Provisional. The v1 interface may be revised without a deprecation window until a second extension beyond the built-in apps is merged. See ADR-003.

## Purpose

Define the v1 contract for adding an enterprise app extension: directory layout, Python hook entry points, and template context variables.

## Directory layout

```text
harness.yaml                    ← app entry (id, vendor, product, environments, routes, nav)
extensions/{app_id}/            ← optional Python hooks package (may be absent)
    __init__.py
    hooks.py                    ← exports render_context() if custom context shaping needed
templates/{app_id}/             ← Jinja2 templates for this app
    home.html                   ← required if a dashboard/home route is declared
    *.html                      ← one file per route that uses a custom template
data/default/{app_id}/          ← seed data (committed to repo)
    {entity}.json               ← one file per data entity declared in harness.yaml routes
static/css/apps/{app_id}.css    ← CSS variable overrides for brand colours
```

All paths are relative to the project root. Extensions without Python hooks need only `templates/`, `data/`, `static/css/apps/`, and a `harness.yaml` entry.

## harness.yaml entry

Minimum required fields:

```yaml
- id: myapp
  vendor: Vendor Name
  product: Product Name
  environments:
    dev:
      host: myapp-dev.local
      base_path: /
  routes:
    - id: home
      path: /
      pattern_type: path
      server_visible: true
      template: home
  nav:
    - label: Home
      route_id: home
      href: /
```

## Python hook: render_context

If an extension needs to add computed values to the template context, it exports a `render_context` function from `extensions/{app_id}/hooks.py`:

```python
def render_context(
    record: dict | None,
    route_id: str,
    env_id: str,
    params: dict[str, str],
) -> dict:
    """Return extra key-value pairs to merge into the Jinja2 template context."""
    ...
```

Return value is merged into the standard context after all built-in keys are set. Hook-supplied keys that conflict with built-in keys are ignored.

The hook is optional. If `hooks.py` is absent or does not export `render_context`, the renderer proceeds with the standard context only.

## Standard template context variables

Every template receives these variables regardless of route type:

| Variable | Type | Description |
|---|---|---|
| `app_id` | `str` | App identifier from `harness.yaml` |
| `app_name` | `str` | `{vendor} {product}` |
| `env_id` | `str` | Environment identifier |
| `env_name` | `str` | Human-readable environment label |
| `base_path` | `str` | `env.base_path` with trailing slash stripped |
| `current_route_id` | `str` | Matched route identifier |
| `params` | `dict[str, str]` | Extracted path / query parameters |
| `nav_items` | `list[NavItem]` | Top-level nav items with children |
| `layout` | `str` | Layout template path (e.g. `layouts/default.html`) |

Routes with a `data_entity` also receive:

| Variable | Type | Description |
|---|---|---|
| `record` | `dict \| None` | Single record (detail routes); `None` if not found |
| `records` | `list[dict]` | All records (list routes) |
| `entity_title` | `str` | Human-readable entity name |
| `list_url` | `str` | URL of the sibling list route (detail routes only) |
| `detail_urls` | `dict[str, str]` | Map of record key → detail URL (list routes only) |

## CSS variable contract

Each app must override the 10 CSS custom properties defined in `static/css/base.css`:

| Variable | Role |
|---|---|
| `--app-primary` | Brand accent / active state |
| `--app-primary-text` | Text on primary-coloured backgrounds |
| `--app-topbar-bg` | Top navigation bar background |
| `--app-topbar-text` | Top nav text colour |
| `--app-sidebar-bg` | Sidebar background |
| `--app-sidebar-text` | Sidebar text colour |
| `--app-sidebar-active` | Selected nav item highlight |
| `--app-sidebar-active-text` | Text on active sidebar item |
| `--app-content-bg` | Main content area background |
| `--app-content-text` | Main content text colour |

## Versioning and stability

The v1 interface covers the directory layout, `render_context` signature, and standard context variable names. Breaking changes require a `v2` designation with a one-release deprecation window. Additive changes (new optional context variable, new optional hook) are non-breaking.
