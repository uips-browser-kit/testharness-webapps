# Runtime CLI Specification

## Glossary

> **Platform CLI** (`harness`): control-plane tool for project lifecycle — init, validate,
> generate-caddy, seed, run, stop. Does not inspect or modify runtime request/response behavior.
> Specified in `docs/specs/cli-spec.md`.
>
> **Runtime CLI** (`harness-cli`): runtime inspection adapter for direct backend access without
> browser automation. Imports only `src.core` and `src.backend`. Does not own HTTP transport or
> HTML rendering.
>
> **"CLI" alone** is ambiguous and must not be used without qualification in specifications,
> PR descriptions, or code comments.

## Purpose

Provide a deterministic, browser-free inspection path for agents and developers who need to:

- Verify that a URL matches the expected route without launching a browser
- Inspect the exact view data that would be rendered for a given route
- Inject, inspect, and remove challenge (delay/fault) state in a running API server

## Package

`src/runtime_cli/` — imports `src.core` and `src.backend` only. Does not import
`src.api` or `src.frontend`. The `route-match` and `view-data` commands are fully local
(no running server required). The `challenge` commands are HTTP client calls to the
running API's `/challenges/...` endpoints.

## Interface contract

### Inputs

| Concept | Flag | Type |
|---------|------|------|
| App identifier | `--app` | str |
| Environment identifier | `--env` | str |
| Route identifier | `--route` | str |
| URL path | `--path` | str |
| Path/query parameters | `--param key=value` | repeatable |
| Output format | `--format json\|table` | str (default: json) |
| API base URL | `--api-url` | str (default: http://localhost:8000) |

### Outputs

All commands default to structured JSON output for agent consumption. Use `--format table`
for human-readable tabular output.

Exit codes:
- `0` — success
- `1` — no match / fault triggered / record not found
- `2` — bad arguments (missing required flag, unknown app/env/route)

## Commands

### route-match

```bash
harness-cli route-match --app salesforce --env dev --path /lightning/r/Account/001/view
```

Resolves which route and parameters a given path matches for the specified app/env.
Fully local — constructs `HarnessService` from `harness.yaml`; no running server needed.

Output (JSON):
```json
{
  "app": "salesforce",
  "env": "dev",
  "route": "account-detail",
  "params": {"id": "001"}
}
```

With `--trace`: also prints each route tried and the match/reject reason.

### view-data

```bash
harness-cli view-data --app salesforce --env dev --route account-detail --param id=001
harness-cli view-data --app salesforce --env dev --route account-detail --param id=001 --format table
```

Loads and shapes the view data for the specified route, as if serving an HTTP request.
Fully local — no running server needed.

Output (JSON, detail route):
```json
{
  "kind": "detail",
  "entity_title": "Accounts",
  "record": { "id": "001", "name": "Rodriguez, Figueroa and Sanchez", ... }
}
```

Output (JSON, list route):
```json
{
  "kind": "list",
  "entity_title": "Accounts",
  "records": [...],
  "detail_urls": {"001": "http://salesforce-dev.local/lightning/r/Account/001/view", ...},
  "detail_key_field": "id"
}
```

With `--dump-context`: wraps the above in an outer object that also includes the full
`RouteContext`.

### challenge set

```bash
harness-cli challenge set --app salesforce --env dev --route account-detail --delay-ms 500
harness-cli challenge set --app salesforce --env dev --route account-detail --fault-kind unavailable --detail "Circuit open"
harness-cli challenge set --app salesforce --env dev --route account-detail --delay-ms 200 --fault-kind server_error
harness-cli challenge set --app salesforce --env dev --route account-detail --delay-ms 500 --duration-s 30
```

Injects a challenge (delay and/or fault) for the specified route via HTTP POST to the
running API. Requires a running server.

Valid `--fault-kind` values: `server_error`, `unavailable`, `business_error`, `not_found`.

`--duration-s N` schedules automatic removal of the challenge after N seconds.

### challenge clear

```bash
harness-cli challenge clear --app salesforce --env dev --route account-detail
```

Removes the active challenge for the specified route via HTTP DELETE.

### challenge list

```bash
harness-cli challenge list
harness-cli challenge list --api-url http://localhost:8000
```

Lists all active challenges from the running API via HTTP GET.

### scenario set

```bash
harness-cli scenario set --app salesforce --env dev --scenario session-expired
```

Sets the active scenario for the specified app/env on the running API. All
subsequent requests to that app/env receive the scenario's configured
delay and fault until cleared. Requires a running server.

### scenario clear

```bash
harness-cli scenario clear --app salesforce --env dev
```

Removes the active scenario for the specified app/env. Subsequent requests
return to normal behaviour (unless a per-route challenge is active).

### scenario list

```bash
harness-cli scenario list
harness-cli scenario list --format table
```

Lists all active scenarios from the running API as a `{app/env: name}` map.

### scenario show

```bash
harness-cli scenario show --app salesforce
```

Reads `harness.yaml` and prints all scenarios defined for the specified app
as structured JSON. Fully local — no running server required.

## API endpoints (backing commands)

### Challenge endpoints

| Command | Method | Path |
|---------|--------|------|
| challenge set | POST | `/challenges/{app_id}/{env_id}/{route_id}` |
| challenge clear | DELETE | `/challenges/{app_id}/{env_id}/{route_id}` |
| challenge list | GET | `/challenges` |

### Scenario endpoints

| Command | Method | Path |
|---------|--------|------|
| scenario set | PUT | `/scenario/{app_id}/{env_id}` |
| scenario clear | DELETE | `/scenario/{app_id}/{env_id}` |
| scenario list | GET | `/scenario` |
| scenario show | — | local only (no HTTP call) |

## Dependency contract

```
src/runtime_cli/ → src/core/     (allowed)
src/runtime_cli/ → src/backend/  (allowed)
src/runtime_cli/ → src/api/      (FORBIDDEN)
src/runtime_cli/ → src/frontend/ (FORBIDDEN)
```

The `challenge` commands use the running API over HTTP — not via Python import.
This satisfies the import boundary while still providing challenge control.
