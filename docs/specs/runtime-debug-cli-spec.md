# Runtime Debug CLI Specification

## Purpose

Provide a developer and agent-facing debug CLI for runtime behavior inspection
without browser automation.

This CLI is separate from Platform CLI:

- Platform CLI: `harness` (init/validate/seed/run/stop)
- Runtime Debug CLI: `harness-debug` (runtime route/data/challenge/debug)

## Scope

In scope:
- route matching diagnostics
- shaped-data inspection
- challenge control and replay
- request simulation and trace retrieval
- test-vector export for browser automation frameworks

Out of scope:
- Docker lifecycle and project scaffolding
- Caddy/infra generation
- frontend implementation details

## Architecture constraints

- Runtime Debug CLI imports only `src.core` and `src.backend`.
- No import dependency on `src.api` or `src.frontend`.
- Challenge set/list/clear may call running API endpoints over HTTP, but that is
  a network contract, not a code dependency.

## Global behavior

Default output format:
- `json`

Global flags:
- `--format json|table` (default `json`)
- `--config PATH` (default `harness.yaml`)
- `--data-set NAME` (override configured data set)
- `--seed INT` (optional deterministic seed override)
- `--verbose`

Exit codes:
- `0` success
- `1` runtime failure or challenge fault triggered (when command semantics require)
- `2` invalid arguments
- `3` no route match / no result
- `4` remote API unavailable (for challenge HTTP commands)

## Commands

## `route-match`

Resolve which app/env/route matches an incoming request shape.

Usage:

```bash
harness-debug route-match \
  --host salesforce-dev.local \
  --path /lightning/r/Account/001/view \
  --method GET \
  --query foo=bar \
  --header X-Harness-App=salesforce \
  --trace
```

Flags:
- `--host TEXT` required
- `--path TEXT` required
- `--method GET|POST|PUT|PATCH|DELETE` default `GET`
- `--query KEY=VALUE` repeatable
- `--header KEY=VALUE` repeatable
- `--trace` include route rejection reasons

Example output:

```json
{
  "matched": true,
  "app_id": "salesforce",
  "env_id": "dev",
  "route_id": "account-detail",
  "params": {"id": "001"},
  "trace": [
    {"route_id": "account-list", "matched": false, "reason": "path-segment-mismatch"},
    {"route_id": "account-detail", "matched": true, "reason": "ok"}
  ]
}
```

## `view-data`

Run backend load+shape and return view data for a route context.

Usage:

```bash
harness-debug view-data \
  --app salesforce \
  --env dev \
  --route account-detail \
  --param id=001
```

Flags:
- `--app TEXT` required
- `--env TEXT` required
- `--route TEXT` required
- `--param KEY=VALUE` repeatable
- `--dump-context` include normalized route context in output

Example output:

```json
{
  "kind": "detail",
  "entity_title": "Accounts",
  "record": {"id": "001", "name": "Acme GmbH"},
  "context": {
    "app_id": "salesforce",
    "env_id": "dev",
    "route_id": "account-detail",
    "params": {"id": "001"}
  }
}
```

## `render-preview`

Produce a rendered HTML artifact for a route context.

Usage:

```bash
harness-debug render-preview \
  --app salesforce --env dev --route account-detail --param id=001 \
  --out .tmp/previews
```

Flags:
- `--app TEXT` required
- `--env TEXT` required
- `--route TEXT` required
- `--param KEY=VALUE` repeatable
- `--out PATH` default `.tmp/previews`

Example output:

```json
{
  "ok": true,
  "template": "salesforce/account_detail.html",
  "artifact_path": ".tmp/previews/salesforce-dev-account-detail-001.html",
  "request_id": "req_01JQX0..."
}
```

## `challenge set`

Set challenge config for a scope.

Usage:

```bash
harness-debug challenge set \
  --app salesforce --env dev --route account-detail \
  --delay-ms 1200 \
  --fault-kind unavailable \
  --detail "Downstream timeout" \
  --probability 0.2 \
  --ttl 300 \
  --api-url http://localhost:8000
```

Flags:
- `--app TEXT` required
- `--env TEXT` required
- `--route TEXT` required
- `--delay-ms INT`
- `--fault-kind TEXT` one of `server_error|unavailable|business_error|not_found`
- `--detail TEXT`
- `--probability FLOAT` range `[0,1]`
- `--seed INT`
- `--ttl INT` seconds
- `--rate-limit-capacity INT`
- `--rate-limit-refill-per-sec FLOAT`
- `--rate-limit-window-sec INT`
- `--rate-limit-retry-after-sec INT`
- `--api-url URL` default `http://localhost:8000`

Example output:

```json
{
  "ok": true,
  "scope": ["salesforce", "dev", "account-detail"],
  "challenge": {
    "delay_ms": 1200,
    "fault": {"kind": "unavailable", "detail": "Downstream timeout"},
    "probability": 0.2,
    "ttl_sec": 300
  }
}
```

## `challenge list`

List active challenge configurations.

Usage:

```bash
harness-debug challenge list --api-url http://localhost:8000
```

Flags:
- `--api-url URL` default `http://localhost:8000`
- `--app TEXT` optional filter
- `--env TEXT` optional filter
- `--route TEXT` optional filter

Example output:

```json
{
  "count": 1,
  "items": [
    {
      "scope": ["salesforce", "dev", "account-detail"],
      "challenge": {"delay_ms": 1200, "fault": {"kind": "unavailable"}}
    }
  ]
}
```

## `challenge clear`

Clear challenge config for one scope or all scopes.

Usage:

```bash
harness-debug challenge clear \
  --app salesforce --env dev --route account-detail \
  --api-url http://localhost:8000
```

Flags:
- `--app TEXT`
- `--env TEXT`
- `--route TEXT`
- `--all` clear all scopes (requires `--confirm`)
- `--confirm` safety confirmation for destructive clear
- `--api-url URL` default `http://localhost:8000`

Example output:

```json
{"ok": true, "cleared": 1}
```

## `challenge replay`

Replay deterministic challenge decisions for debugging.

Usage:

```bash
harness-debug challenge replay \
  --app salesforce --env dev --route account-detail \
  --seed 12345 --stream latency-main --draw-index 7
```

Flags:
- `--app TEXT` required
- `--env TEXT` required
- `--route TEXT` required
- `--seed INT` required
- `--stream TEXT` required
- `--draw-index INT` required

Example output:

```json
{
  "ok": true,
  "outcome": {
    "delay_ms": 4820,
    "fault_kind": null,
    "mutations": []
  }
}
```

## `request simulate`

Execute a synthetic request through match, prepare, challenge policy, and
outcome mapping diagnostics.

Usage:

```bash
harness-debug request simulate \
  --host salesforce-dev.local \
  --path /lightning/r/Account/001/view \
  --method GET \
  --seed 12345
```

Flags:
- `--host TEXT` required
- `--path TEXT` required
- `--method TEXT` default `GET`
- `--query KEY=VALUE` repeatable
- `--header KEY=VALUE` repeatable
- `--seed INT`
- `--trace`

Example output:

```json
{
  "request_id": "req_01JQX0...",
  "match": {"app_id": "salesforce", "env_id": "dev", "route_id": "account-detail"},
  "view_kind": "detail",
  "challenge": {"applied": true, "delay_ms": 1200, "fault_kind": "unavailable"},
  "api_mapping": {"status_code": 503, "retriable": true}
}
```

## `trace get`

Fetch one stored trace by request id.

Usage:

```bash
harness-debug trace get --request-id req_01JQX0... --api-url http://localhost:8000
```

Flags:
- `--request-id TEXT` required
- `--api-url URL` default `http://localhost:8000`

## `trace last`

Fetch latest N traces.

Usage:

```bash
harness-debug trace last --limit 20 --api-url http://localhost:8000
```

Flags:
- `--limit INT` default `10`
- `--api-url URL` default `http://localhost:8000`

## `assert contract`

Assert response/debug invariants for a route/scenario.

Usage:

```bash
harness-debug assert contract \
  --app salesforce --env dev --route account-detail \
  --expect-status 503 \
  --expect-retriable true
```

Flags:
- `--app TEXT` required
- `--env TEXT` required
- `--route TEXT` required
- `--param KEY=VALUE` repeatable
- `--expect-status INT`
- `--expect-retriable true|false`
- `--expect-error-kind TEXT`

Example output:

```json
{"ok": true, "assertions": 3, "failed": 0}
```

## `scenario run`

Run a named scenario over a route set and return a summary.

Usage:

```bash
harness-debug scenario run \
  --scenario long-tail-latency \
  --app salesforce --env dev \
  --route account-list --route account-detail \
  --iterations 50 --seed 9001
```

Flags:
- `--scenario TEXT` required
- `--app TEXT` required
- `--env TEXT` required
- `--route TEXT` repeatable
- `--iterations INT` default `10`
- `--seed INT`

## `scenario soak`

Run randomized scenario stress checks with invariant assertions.

Usage:

```bash
harness-debug scenario soak \
  --scenario throttle-burst \
  --app salesforce --env dev \
  --iterations 500 \
  --seed-start 1000
```

Flags:
- `--scenario TEXT` required
- `--app TEXT` required
- `--env TEXT` required
- `--iterations INT` default `100`
- `--seed-start INT` default `1`
- `--max-failures INT` default `10`

## `test-vector export`

Export deterministic test vectors for Playwright/Puppeteer/Selenium suites.

Usage:

```bash
harness-debug test-vector export \
  --app salesforce --env dev \
  --route account-list --route account-detail \
  --scenario stable-baseline \
  --seed 4242 \
  --out tests/vectors/salesforce-dev.json
```

Flags:
- `--app TEXT` required
- `--env TEXT` required
- `--route TEXT` repeatable
- `--scenario TEXT` required
- `--seed INT` required
- `--out PATH` required

Example output:

```json
{
  "ok": true,
  "vectors": 24,
  "out": "tests/vectors/salesforce-dev.json"
}
```

## JSON output contract (minimum)

All commands should include:

```json
{
  "ok": true,
  "command": "route-match",
  "timestamp": "2026-05-28T12:00:00Z"
}
```

On failures:

```json
{
  "ok": false,
  "error": {
    "code": "NO_ROUTE_MATCH",
    "message": "No route matched host/path input"
  }
}
```

## Non-functional requirements

- Command execution should be deterministic when `--seed` is provided.
- Output must be machine-parseable JSON by default.
- No browser dependency for core debug commands.
- Commands must complete within reasonable local debug latency:
  - `route-match`, `view-data`: < 500ms typical
  - `scenario soak`: bounded by iterations and explicit timeout settings

## Future extensions

- `wait-ready` command for CI pipelines
- artifact bundle export (`html + trace + challenge outcome`)
- scenario profile import from catalog files
