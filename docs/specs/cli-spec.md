# CLI Specification

## Purpose

Provide the developer control plane for the local test platform.

## Owns

- project initialization
- config validation
- Caddy config generation
- data seeding
- Docker orchestration commands

## Does not own

- runtime service behavior
- app rendering
- OAuth/OIDC behavior

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
* variants
* idp config
* templates
* data references

### Generate Caddy

```bash
harness generate-caddy
```

Reads:

```text
config/environments.yaml
config/routes.yaml
```

Writes:

```text
infra/caddy/generated/Caddyfile
```

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
