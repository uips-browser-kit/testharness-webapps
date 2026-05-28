# Challenge Catalog Specification

## Purpose

Define a standard catalog of runtime challenges that make harness apps behave like
real corporate systems for RPA business-process automation testing.

This catalog is used by backend challenge policies and consumed through API and
Runtime Debug CLI controls.

## Scope

In scope:
- deterministic and randomized challenge injection
- route/app/env-scoped challenge selection
- transport-neutral challenge outcomes in backend
- reproducible test behavior with seed and replay

Out of scope:
- frontend rendering implementation details
- HTTP status mapping rules (owned by API layer)
- vendor-specific business logic beyond declared scenario configs

## Terms

- Challenge: a configured behavior modifier applied to request handling.
- Scenario: named collection of challenges with activation rules.
- Outcome: actual sampled effect for a request (delay, fault, mutation, etc.).
- Replay: re-running with the same seed and draw index sequence.

## Architecture constraints

- Challenge decision logic lives in backend (`HarnessService` / policy layer).
- API maps backend outcomes to HTTP; API does not decide challenge policy.
- Runtime Debug CLI can set/list/clear scenarios but must not import API/frontend.

## Challenge model

```yaml
id: string                        # unique scenario id
description: string
enabled: boolean
scope:
  app_id: string
  env_id: string
  route_id: string
activation:
  mode: always | probability | schedule
  probability: 0.0-1.0            # required if mode=probability
  schedule: cron-or-window        # optional if mode=schedule
randomness:
  seed: integer | null            # null = runtime default seed
  stream: string                  # stable stream id, e.g. "latency-main"
effects:
  latency:
    min_ms: integer
    max_ms: integer
    distribution: uniform | normal | p95_spike
    timeout_ms: integer | null
  fault:
    kind: none | server_error | unavailable | business_error | not_found
    detail: string
    retriable: boolean
  data_quality:
    null_rate: 0.0-1.0
    field_drift:
      - field: string
        from: string
        to: string
    omit_fields: [string]
  workflow:
    extra_step_rate: 0.0-1.0
    conditional_required_fields: [string]
    transient_validation_error_rate: 0.0-1.0
  rate_limit:
    enabled: boolean
    algorithm: token_bucket | fixed_window
    capacity: integer               # max tokens / window capacity
    refill_per_sec: number          # token_bucket only
    window_sec: integer             # fixed_window only
    cost_per_request: integer       # default 1
    key_by: app | env | route | client
    retry_after_sec: integer
limits:
  max_delay_ms: integer
  max_fault_rate: 0.0-1.0
observability:
  emit_metrics: boolean
  include_trace: boolean
```

## Outcome model

```yaml
scenario_id: string
scope_key: [app_id, env_id, route_id]
request_id: string
seed: integer
stream: string
draw_index: integer
applied:
  delay_ms: integer
  fault_kind: string | null
  mutations: [string]
timestamp: iso-8601
```

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
- `server_error`
- `unavailable`
- `not_found`

Guideline: default retriable behavior for `unavailable`; non-retriable for
`business_error`.

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

### 7. Rate limiting

Intent: emulate platform throttling and quota protections.

Examples:
- burst traffic exceeds route quota
- tenant/app-level throughput cap reached
- temporary throttling with retry hint

Guideline: challenge outcome should include a transport-neutral throttle marker;
API maps this to HTTP `429` and `Retry-After` when applicable.

## Randomness and reproducibility

Rules:
- Every scenario must support explicit seed override.
- If seed omitted, service seed is used and logged in outcome.
- RNG stream is stable per scenario id + scope key.
- Draw index increments deterministically per decision point.

Testing modes:
- Deterministic mode: fixed seed, exact expected outcomes.
- Soak mode: rotating seeds, assert invariants only.

Replay:
- Replay by `seed + stream + draw_index` sequence.
- Replay artifacts should be exportable as JSON lines.

## Safety limits

Required guards:
- hard cap on `delay_ms` (default 10_000)
- hard cap on active fault rate per route (default 0.5)
- optional scenario TTL
- emergency disable switch per app/env/route
- hard cap on `retry_after_sec` (default 300)

## Metrics and logs

Minimum metrics:
- `harness_challenge_applied_total{app,env,route,scenario,effect}`
- `harness_challenge_delay_ms_bucket{app,env,route,scenario}`
- `harness_challenge_fault_total{app,env,route,scenario,fault_kind}`
- `harness_challenge_rate_limited_total{app,env,route,scenario,key}`

Log fields:
- request id
- scope key
- scenario id
- seed / stream / draw index
- applied effects
- rate-limit key and remaining budget (if rate_limit applied)

## API and CLI contract notes

API endpoints (example):
- `POST /challenges/{app_id}/{env_id}/{route_id}`
- `DELETE /challenges/{app_id}/{env_id}/{route_id}`
- `GET /challenges`

Runtime Debug CLI commands (example):
- `harness-debug challenge set ...`
- `harness-debug challenge clear ...`
- `harness-debug challenge list`

Rate-limit config can be set via the same challenge payload using
`effects.rate_limit`.

## Default scenario catalog (v1)

- `stable-baseline`
  - no fault, low latency jitter
- `intermittent-503`
  - 10% unavailable faults, medium latency
- `long-tail-latency`
  - p95 spike profile, no faults
- `data-drift-lite`
  - low null rate + minor format drift
- `workflow-friction`
  - intermittent extra step + transient validation errors
- `conflict-heavy`
  - business_error conflicts on update-like routes
- `throttle-burst`
  - token bucket limit with short retry-after hints

## Versioning

- Catalog version field: `catalog_version` (semver).
- Backward-compatible additions: new optional fields, new preset ids.
- Breaking changes: field removals/renames require major version bump.

## Acceptance criteria

- Backend can apply catalog scenarios deterministically with seed/replay.
- API responses remain deterministic mappings from backend outcomes.
- Runtime Debug CLI can set/list/clear scenarios by scope.
- Tests include deterministic and soak profiles.
