# Architecture

## 1. System context

Who uses the system and what external infrastructure it depends on.

```mermaid
C4Context
    title System Context — testharness-webapps

    Person(dev, "Developer / UiPath", "Runs browser or UiPath automation against enterprise-shaped URLs")
    System(platform, "testharness-webapps", "Local platform mimicking enterprise web apps at realistic URLs")
    System_Ext(hosts, "OS hosts file", "Maps .local hostnames to 127.0.0.1")
    System_Ext(docker, "Docker Desktop", "Container runtime for platform services")

    Rel(dev, platform, "Navigates to", "HTTPS")
    Rel(platform, hosts, "Requires entries in")
    Rel(docker, platform, "Hosts")
```

---

## 2. Containers

The running processes and the protocols between them.

```mermaid
C4Container
    title Containers — testharness-webapps

    Person(dev, "Developer / UiPath")

    Container_Boundary(platform, "testharness-webapps") {
        Container(caddy, "Caddy", "Reverse proxy", "Host routing · TLS termination · header injection")
        Container(harness, "Harness", "Python · ASGI", "App mimics · URL routing · page rendering · metrics")
        Container(keycloak, "Keycloak", "Java · Docker", "OAuth 2.0 / OIDC · realm · tokens · session")
        Container(prometheus, "Prometheus", "Docker", "Metric scraping · storage · querying")
    }

    Rel(dev, caddy, "HTTPS", "443 / 80")
    Rel(caddy, harness, "HTTP", "8000")
    Rel(caddy, keycloak, "HTTP", "8080")
    Rel(caddy, prometheus, "HTTP", "9090")
    Rel(harness, prometheus, "Exposes /metrics", "HTTP")
```

---

## 3. Harness components

Internal building blocks of the Harness process.

```mermaid
C4Component
    title Components — Harness

    Container_Boundary(h, "Harness") {
        Component(loader, "Config Loader", "Python", "Reads harness.yaml into App / Route / Environment objects")
        Component(router, "Router", "Python", "Matches incoming URL to App + Route + extracted params")
        Component(variant, "Variant Engine", "Python", "Selects and applies variant context per request")
        Component(data, "Data Loader", "Python", "Reads data/{set}/{app}/*.json records")
        Component(renderer, "Template Renderer", "Jinja2", "Binds records and variant context to HTML templates")
        Component(metrics, "Metrics Emitter", "prometheus-client", "Request counters and duration histograms at /metrics")
        Component(ext, "Extension Registry", "Python", "Discovers and loads per-app extensions from extensions/")
    }

    Rel(router, loader, "Reads config from")
    Rel(router, variant, "Resolves active variants via")
    Rel(router, metrics, "Records request to")
    Rel(renderer, data, "Loads records from")
    Rel(renderer, ext, "Resolves templates via")
    Rel(router, renderer, "Delegates page rendering to")
```

---

## 4. Request flow

### Happy path

```mermaid
sequenceDiagram
    autonumber
    participant B  as Browser / UiPath
    participant C  as Caddy
    participant R  as Router
    participant V  as Variant Engine
    participant D  as Data Loader
    participant T  as Template Renderer
    participant M  as Metrics Emitter
    participant P  as Prometheus

    B->>C: GET sf-dev.local/lightning/r/Account/001/view
    C->>R: forward + inject X-Harness-App, X-Harness-Environment, X-Request-Id
    R->>R: match URL → app=salesforce, route=account-detail, params={id: "001"}
    R->>V: resolve active variants (header / config / default)
    V-->>R: variant context
    R->>D: load record id=001 from data/default/salesforce/accounts.json
    D-->>R: account record
    R->>T: render account.html with record + variant context
    T-->>R: HTML
    R->>M: harness_request_total{app, route, variant, status=200}++
    R-->>C: 200 HTML
    C-->>B: 200 HTML
    P-->>M: scrape /metrics every 15 s
```

### Trust boundary

Harness **only trusts** `X-Harness-*` headers that arrive from Caddy. Any client-supplied values for these headers are overwritten by Caddy before forwarding. Port `8000` is internal to the Docker network and not reachable from the host directly — all external traffic enters through Caddy on `80`/`443`.

**Verifiable control:** `harness validate --security` (or the CI smoke-test target) must assert that a direct HTTP request to `localhost:8000` with a spoofed `X-Harness-App` header is either refused or returns the same result as a request without that header — confirming Caddy's overwrite is the only trusted source. This check runs as part of `harness run` startup validation.

### Error flows

| Condition | HTTP status | Metric label | Behaviour |
|-----------|-------------|--------------|-----------|
| No route matches host + path | `404` | `status=404` | Router returns a plain 404 page; no template render attempted |
| Route matched, record not found in data | `422` | `status=422` | Renderer returns a stub page with placeholder fields |
| Template render error | `500` | `status=500` | Harness returns an error page; exception logged with `request_id` |
| Incompatible variants requested | `409` | `status=409` | Variant Engine rejects before render; no data load |
| Extension load failure at startup | — | — | Harness refuses to start; error written to stdout |

All non-200 responses still increment `harness_request_total` with the appropriate `status` label so error rates are queryable in Prometheus.

---

## 5. Package structure

```text
testharness-webapps/
  src/
    core/         App · Route · Environment · PatternType
                  Config Loader · URL Resolver · URL Matcher
    harness/      ASGI app · Router · Variant Engine
                  Data Loader · Template Renderer · Metrics Emitter
                  Server CLI entry point
    cli/          Developer CLI
                  init · validate · generate-caddy · generate-prometheus
                  seed · idp export/import · run · stop

  extensions/     Per-app Python hooks and extension metadata
  templates/      Per-app Jinja2 templates  (templates/{app}/*.html)
  data/
    default/      Static seed=42 dataset; IDs match fixture params (committed)
    dynamic/      Generated at runtime (gitignored)
  config/
    harness.yaml
  infra/
    caddy/
    keycloak/     harness-realm.json
    prometheus/   prometheus.yml
    docker-compose.yml
  scripts/        Spike and generation scripts
  tests/
    fixtures/     YAML resolve · match · profile cases per app
```

---

## 6. Dependency rules

Core is the only shared foundation. Harness, CLI, and Caddy depend on Core. No service imports code from another service; runtime dependencies between services are via explicit network contracts only.

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "background":          "#002b36",
    "mainBkg":             "#073642",
    "primaryColor":        "#073642",
    "primaryBorderColor":  "#586e75",
    "primaryTextColor":    "#839496",
    "lineColor":           "#586e75",
    "edgeLabelBackground": "#002b36",
    "titleColor":          "#93a1a1"
  }
}}%%
graph LR
    classDef core    fill:#073642,stroke:#268bd2,color:#268bd2,font-weight:bold
    classDef service fill:#073642,stroke:#2aa198,color:#93a1a1
    classDef error   fill:#073642,stroke:#dc322f,color:#dc322f,stroke-dasharray:4 3

    Core:::core -->|"owns contracts"| Harness:::service
    Core:::core -->|"owns contracts"| CLIdev["CLI · developer"]:::service
    Core:::core -->|"owns contracts"| CLIsrv["CLI · server"]:::service
    Core:::core -->|"owns contracts"| Caddy:::service

    Harness:::error  -.->|"✕"| CLIdev
    CLIdev           -.->|"✕"| Harness:::error
    CLIdev           -.->|"✕"| Caddy:::error
```

---

## 7. Extension model

Adding a new enterprise application requires no changes to Core or Harness:

```text
config/harness.yaml          ← add app entry
extensions/{app}/            ← optional Python hooks
templates/{app}/*.html       ← Jinja2 templates
data/default/{app}/*.json    ← seed data (committed)
```

---

## 8. Quality attributes

| Attribute | Mechanism |
|-----------|-----------|
| **Extensibility** | Extension registry; new app needs no core changes |
| **Reproducibility** | Seeded Faker (`seed=42`); `data/default/` committed; deterministic variants |
| **Isolation** | Services communicate through explicit interfaces only; no cross-service imports |
| **Local-first** | Docker Compose + OS hosts file; no internet dependency at runtime |
| **Observability** | Prometheus metrics at `/metrics` (labels: app, route, variant, status, duration); structured logs per request with `request_id`, app, route, variant, status, duration\_ms |

---

## 9. Ports

| Service    | Port     |
|------------|----------|
| Harness    | 8000     |
| Keycloak   | 8080     |
| Prometheus | 9090     |
| Caddy      | 80 / 443 |

---

## 10. Architecture decisions

Key decisions are recorded as ADRs in [`docs/adr/`](adr/):

| ID | Decision |
|----|----------|
| [ADR-001](adr/001-single-harness-yaml.md) | Single `harness.yaml` over per-service config files |
| [ADR-002](adr/002-keycloak.md) | Keycloak over a custom IdP implementation |
| [ADR-003](adr/003-extension-model.md) | Additive extension model — no core changes per app |
| [ADR-004](adr/004-uv-workspace.md) | uv workspace with parent venv |
| [ADR-005](adr/005-response-contracts.md) | Response and metric semantics are stable contracts |
