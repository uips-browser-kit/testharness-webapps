# Platform CLI Specification

## Glossary

> **Platform CLI** (`harness`): control-plane tool for project lifecycle — init, validate,
> generate-caddy, seed, run, stop. Does not inspect or modify runtime request/response behavior.
>
> **Runtime CLI** (`harness-cli`): runtime inspection adapter for direct backend access without
> browser automation. Imports only `src.core` and `src.backend`. Does not own HTTP transport or
> HTML rendering. Specified in `docs/specs/runtime-cli-spec.md`.
>
> **"CLI" alone** is ambiguous and must not be used without qualification in specifications,
> PR descriptions, or code comments.

## Purpose

Provide the developer control plane for the local test platform.

## Package

`src/platform_cli/` — imports `src.core` only. Does not import `src.backend`, `src.api`,
or `src.frontend`. Does not own runtime serving behavior.

## Owns

- project initialization
- config validation
- Caddy config generation
- data seeding
- Docker orchestration commands

## Does not own

- runtime service behavior (request handling, response rendering, challenge injection)
- app HTML rendering
- OAuth/OIDC behavior
- runtime route inspection or view-data access (those belong to the Runtime Debug CLI)

## Commands

### Init

```bash
harness init
```

Creates starter config and folders.

### Validate

```bash
harness validate
```

Validates:

* apps
* routes
* environments
* idp config
* templates
* data references

### Generate Caddy

```bash
harness generate-caddy
```

Reads `harness.yaml` and writes `infra/caddy/generated/Caddyfile`.

### Seed data

```bash
harness seed
```

Generates deterministic synthetic data.

Options:

```bash
--app salesforce
--seed 12345
```

### Run

```bash
harness run
```

Starts local Docker Compose.

### Stop

```bash
harness stop
```

Stops local services.

## Exit codes

```text
0 success
1 validation failure
2 config missing
3 docker failure
4 generation failure
```
