# testharness-webapps

Local platform that mimics enterprise web apps at realistic URLs so browser and UiPath automation can be tested without hitting production.

## What it provides

- **12 app mimics** — Salesforce, Dynamics 365, ServiceNow, SAP Fiori, Oracle Fusion, Workday, Jira, Confluence, SharePoint, Power BI, Tableau, Power Apps
- **Realistic URLs** — path, query-only, hash, and protocol patterns per app
- **Test fixtures** — YAML resolve/match/profile cases in `tests/fixtures/`
- **Test data** — Faker-generated JSON records in `data/` keyed to fixture IDs

## Services

| Service | Port | Role |
|---------|------|------|
| Harness | 8000 | App mimics, URL routing, page rendering |
| Keycloak | 8080 | OAuth/OIDC, login flow, tokens |
| Prometheus | 9090 | Metrics scraping and storage |
| Caddy | 80/443 | Host routing, HTTPS, header injection |

## Quick start

```sh
just run python scripts/catalog_urls.py     # print all resolved URLs
just run python scripts/generate_fixtures.py  # regenerate tests/fixtures/
just run python scripts/generate_data.py      # regenerate data/default/
just run python scripts/generate_data.py --set dynamic --seed 0 --count 100
```

## Layout

```
scripts/
  catalog_urls.py       — URL patterns for all 12 apps (source of truth)
  generate_fixtures.py  — produces tests/fixtures/ from catalog_urls
  generate_data.py      — produces data/ using Faker

tests/fixtures/
  apps/{slug}/          — profile.yaml, resolve.yaml, match.yaml
  configs/valid/        — minimal, multi-app, full harness.yaml examples
  configs/invalid/      — one file per validation rule violation

data/
  default/              — static set committed; IDs match fixture params
  dynamic/              — gitignored; generated at runtime

docs/
  architecture.md
  url-pattern-taxonomy.md
  app-profile-catalog.md
  specs/
```

## Adding a package

```sh
just add <package>      # installs into parent workspace venv
```
