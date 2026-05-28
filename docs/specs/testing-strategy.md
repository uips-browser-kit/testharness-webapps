# Testing Strategy

## Purpose

Define the four-layer test pyramid used in testharness-webapps, with examples of each layer and references to the relevant fixture files.

## Pyramid overview

```text
         ┌─────────────────────┐
         │       E2E           │  Playwright against full stack (planned)
         ├─────────────────────┤
         │    Integration      │  HTTP against live FastAPI TestClient
         ├─────────────────────┤
         │  Fixture-driven     │  YAML fixtures exercising route matching
         ├─────────────────────┤
         │       Unit          │  Pure functions, no I/O
         └─────────────────────┘
```

## Layer 1: Unit tests

Pure-function tests with no I/O, no database, no HTTP.

**What belongs here:**
- `src/core/` — matcher, resolver, config loader, model constructors
- `src/backend/` — shaper, data loader (mocked file reads)
- Utility functions

**Test files:**
- `tests/test_core_match.py` — path pattern matching, query-param matching
- `tests/test_core_resolve.py` — URL resolution for all pattern types
- `tests/test_core_config.py` — harness.yaml parsing
- `tests/test_shaper.py` — DetailViewData / ListViewData construction

**Run:**
```text
uv run pytest tests/test_core_*.py tests/test_shaper.py -q
```

## Layer 2: Fixture-driven tests

Parameterised tests driven by YAML fixture files. Each fixture captures a route-match scenario (input path + expected route + expected params) so test coverage grows without code changes.

**What belongs here:**
- Route matching across all 12 apps and all pattern types
- Edge cases from real URL patterns added to fixtures rather than inline test code

**Fixture location:** `tests/fixtures/`

**Test files:**
- `tests/test_match_data.py` — parameterised over YAML fixture files

**Run:**
```text
uv run pytest tests/test_match_data.py -q
```

## Layer 3: Integration tests

HTTP-level tests using FastAPI's `TestClient`. The full application stack (routing, data loading, shaping, rendering, challenge pipeline) runs in-process with no mocking.

**What belongs here:**
- Full request → response cycles
- Content negotiation (Accept header, `?format=`)
- Challenge injection (delay, fault kinds)
- Metrics endpoint
- Error responses (404, 406, 503, etc.)
- Runtime CLI commands via `CliRunner`

**Test files:**
- `tests/test_router.py` — route resolution over HTTP
- `tests/test_renderer.py` — HTML rendering correctness
- `tests/test_content_negotiation.py` — Accept-header negotiation
- `tests/test_pipeline.py` — challenge delay and fault injection
- `tests/test_error_responses.py` — 4xx / 5xx response shapes
- `tests/test_metrics.py` — Prometheus metrics endpoint
- `tests/test_runtime_cli.py` — Typer CLI commands
- `tests/test_integration.py` — cross-cutting end-to-end scenarios

**Mark:** integration tests are marked `@pytest.mark.integration` and can be excluded with `-m "not integration"`.

**Run:**
```text
uv run pytest -m "not integration" -q   # fast: unit + fixture + most integration
uv run pytest -q                         # full suite including live-server integration tests
```

## Layer 4: E2E tests (planned)

Full-stack tests using Playwright against a running Docker Compose environment. Not yet implemented.

**Planned scope:**
- Browser navigation through all 12 app simulations
- Active nav highlighting
- Challenge injection visible in the browser (latency, fault pages)
- Keycloak login flow

**Location (planned):** `tests/e2e/`

## Fixture data

Seed data committed to the repo at `data/default/{app}/{entity}.json` is the stable fixture baseline. Generated with:

```text
uv run python scripts/generate_data.py --set default
```

The first record in each entity file uses IDs matching the `SAMPLE_PARAMS` anchor in `harness.yaml` so that detail-page integration tests resolve to a known record without dynamic lookup.

## Import linter

Import boundary rules are enforced by `import-linter`:

```text
uv run lint-imports
```

Five contracts are defined in `pyproject.toml`. All must pass before merge.
