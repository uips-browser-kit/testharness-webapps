# Challenge Catalog Specification

## Purpose

Define named scenarios that make harness apps behave like real corporate systems
for UiPath library development and RPA automation testing.

A developer puts an app into a named condition (e.g. `session-expired`) and runs
their UiPath workflow against it. The harness responds to every matching request
with the scenario's configured delay and/or fault until the scenario is cleared.

## Scope

In scope:
- Named scenario definitions pre-declared per app in `harness.yaml`
- Per-app/env persistent activation via API
- Per-request header-based activation for parallel test runners
- Existing per-route challenge injection (kept alongside)

Out of scope:
- Frontend rendering implementation details
- HTTP status mapping rules (owned by API layer)
- Probabilistic/seeded random activation (not implemented)

## Terms

- **Scenario**: a named condition pre-declared in `harness.yaml` for an app.
- **Challenge**: a configured delay and/or fault applied to a specific route.
  Kept as the lower-level primitive; scenarios build on it.
- **Persistent activation**: `PUT /scenario/{app}/{env}` sets the active scenario
  for all subsequent requests to that app/env until cleared.
- **Per-request activation**: `X-Harness-Scenario: <name>` header applies the
  scenario to that request only; no server state stored.

## Architecture constraints

- `ScenarioDefinition` and `ScenarioMap` live in `src.core.models`.
- `ScenarioStore` protocol and `InMemoryScenarioStore` live in `src.backend.service`.
- `HarnessService` resolves scenarios; API maps them to HTTP.
- Runtime CLI uses HTTP to set/clear scenarios; it does not import `src.api`.

## Scenario model (harness.yaml)

```yaml
scenarios:
- name: session-expired           # unique per app; used in API and CLI
  description: Auth session has expired mid-flow
  delay_ms: 0                     # optional; default 0
  fault:
    kind: auth_error              # see Fault kinds below
    detail: "Session expired — re-authentication required"
    retriable: false              # optional; default false
```

## Activation and precedence

Highest priority wins for each request:

| Priority | Activation | Scope |
|----------|-----------|-------|
| 1 (highest) | `X-Harness-Scenario` request header | single request |
| 2 | Per-route challenge (`POST /challenges/...`) | per-route, persistent |
| 3 | Active scenario (`PUT /scenario/...`) | per-app/env, persistent |
| 4 (lowest) | No effect | normal behaviour |

The per-request header (`X-Harness-Scenario`) is intended for parallel test
runners that cannot coordinate persistent state without interfering with each other.

An unknown scenario name in the header is silently ignored — the request proceeds
normally. This prevents accidental failures when a test runner sends a stale name.

## Challenge categories

### 1. Latency instability

Intent: emulate slow enterprise backends and tail latency.

Baseline presets:
- `latency-low`: 100-400ms
- `latency-medium`: 400-1500ms
- `latency-high-tail`: 200-600ms with 5-10% spikes to 4-8s

### 2. Availability and server faults

Intent: emulate intermittent outages and degraded dependencies.

Fault kinds:
- `server_error` → HTTP 500
- `unavailable` → HTTP 503 (retriable)
- `not_found` → HTTP 404
- `rate_limit` → HTTP 429 (retriable)
- `auth_error` → HTTP 401
- `forbidden` → HTTP 403
- `business_error` → HTTP 409

Guideline: `unavailable` and `rate_limit` are retriable; all others are not
unless `retriable: true` is explicitly set on the fault.

### 3. Business-process faults

Intent: emulate process-level failures that automation must handle.

Examples:
- duplicate submission conflict
- stale-record update conflict
- approval required branch
- policy violation requiring correction

### 4. Data quality drift

Intent: emulate real-world data inconsistencies.

Examples:
- optional fields become null
- identifier format changes
- partial records (missing optional/expected fields)

### 5. Workflow friction

Intent: emulate UI/process variability without browser automation coupling.

Examples:
- intermittent extra confirmation step
- conditionally required fields
- transient validation failures

### 6. Session/auth friction

Intent: emulate operational auth/session disruption.

Examples:
- session expiry mid-flow
- forced re-auth marker in outcome
- token refresh required marker

Note: backend emits transport-neutral markers; API decides HTTP mapping.

Implementation hints:
- Model explicit auth tripwires (not only timeout-driven behavior):
  - `force_logout`
  - `invalidate_session`
  - `require_reauth`
- Add trigger modes suitable for deterministic testing:
  - `on_request_n` (fire exactly on the Nth matching request)
  - `probability` (seeded RNG + stream + draw index)
  - optional route/app/env match constraints
- Keep challenge decisions in backend; do not place decision logic in API middleware.
- Include replay metadata in every applied outcome:
  - `seed`, `stream`, `draw_index`, and `trigger_reason`
- API mapping should remain deterministic and explicit:
  - map auth outcomes to HTTP (`401`/`403`) or auth-flow hints
  - include request correlation id in error payload/page
- Runtime Debug CLI should expose set/list/clear/replay for auth tripwires.

### 7. Rate limiting

Intent: emulate platform throttling and quota protections.

Examples:
- burst traffic exceeds route quota
- tenant/app-level throughput cap reached
- temporary throttling with retry hint

Guideline: challenge outcome should include a transport-neutral throttle marker;
API maps this to HTTP `429` and `Retry-After` when applicable.

## API and CLI contract

### Scenario API endpoints

| Command | Method | Path |
|---------|--------|------|
| Set active scenario | PUT | `/scenario/{app_id}/{env_id}` body: `{"scenario": "<name>"}` |
| Clear active scenario | DELETE | `/scenario/{app_id}/{env_id}` |
| Show active scenario | GET | `/scenario/{app_id}/{env_id}` |
| List all active scenarios | GET | `/scenario` |

Setting an unknown scenario name returns HTTP 404. Setting with a missing
`scenario` field returns HTTP 422.

### Challenge API endpoints (per-route, unchanged)

| Command | Method | Path |
|---------|--------|------|
| Set challenge | POST | `/challenges/{app_id}/{env_id}/{route_id}` |
| Clear challenge | DELETE | `/challenges/{app_id}/{env_id}/{route_id}` |
| List challenges | GET | `/challenges` |

### Runtime CLI commands

```bash
harness-cli scenario set --app salesforce --env dev --scenario session-expired
harness-cli scenario clear --app salesforce --env dev
harness-cli scenario list
harness-cli scenario show --app salesforce   # local only, reads harness.yaml
```

## Salesforce scenario catalog

Defined in `harness.yaml` under the `salesforce` app:

| Name | Fault kind | HTTP | Description |
|------|-----------|------|-------------|
| `session-expired` | `auth_error` | 401 | Auth session has expired mid-flow |
| `rate-limited` | `rate_limit` | 429 | API quota exceeded |
| `degraded` | `unavailable` | 503 | Backend intermittently unavailable (1500 ms delay) |
| `record-locked` | `business_error` | 409 | Record locked by another user |

## Testability guidance

- Use `PUT /scenario/{app}/{env}` for focused single-developer iteration.
- Use `X-Harness-Scenario` header for parallel test runners — each runner
  sends its own header; no shared server state needed.
- Route challenges override scenarios — use them for route-specific pinning
  while a scenario is active on the same app/env.

## Acceptance criteria

- Scenarios defined in `harness.yaml` are loaded by config parser.
- `PUT /scenario/...` activates a scenario for all routes in that app/env.
- `X-Harness-Scenario` header activates a scenario for that request only.
- Route challenges take priority over scenarios.
- Unknown header scenario name is silently ignored (returns 200).
- `harness-cli scenario show` lists defined scenarios without a running server.
