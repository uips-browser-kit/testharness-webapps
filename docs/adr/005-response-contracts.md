# ADR-005: Response and metric semantics are stable contracts

## Status

Accepted

## Context

`architecture.md` defines error semantics (404/422/409/500) and metric labels for the Harness. Without an explicit stability commitment these can drift silently — a refactor changes a status code, fixture tests are not updated, and automation that relies on specific responses breaks in non-obvious ways.

## Decision

The HTTP status codes, metric label values, and error page behaviour defined in `architecture.md §4 Error flows` are treated as **stable contracts**, equivalent to a public API. Changes require:

1. An ADR update or superseding ADR.
2. Updated fixture tests in `tests/fixtures/configs/` covering the affected status.
3. A `BREAKING` marker in the relevant commit message if backward compatibility is broken.

The canonical status-to-behaviour mapping is:

| Status | Condition | Metric `status` label |
|--------|-----------|----------------------|
| `200` | Route matched, record found, render succeeded | `200` |
| `404` | No route matches host + path | `404` |
| `409` | Incompatible variants requested | `409` |
| `422` | Route matched, record not found in data | `422` |
| `500` | Template render error or unhandled exception | `500` |

Every status code in this table **must** have a corresponding fixture in `tests/fixtures/configs/` that exercises that path and asserts the status label in emitted metrics.

## Consequences

- Accidental status-code drift is caught by CI before merge.
- Adding a new error condition requires a fixture — behaviour is documented by test, not only by prose.
- Fixture suite grows with each new error path; this is intentional.
