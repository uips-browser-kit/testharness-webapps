# ADR-001: Single harness.yaml over per-service config files

## Status

Accepted

## Context

Early drafts split configuration across five files: `apps.yaml`, `routes.yaml`, `environments.yaml`, `variants.yaml`, `idp.yaml`. Each service read its own file independently, which created duplication and required cross-file consistency checks (e.g. a route referencing a variant defined elsewhere).

## Decision

Consolidate all platform configuration into a single `config/harness.yaml` with top-level sections: `apps`, `variants`, `keycloak`, `prometheus`, `caddy`.

## Consequences

- One file to validate, one file to version-control.
- The CLI generates per-service config (Caddyfile, `prometheus.yml`, realm JSON) from `harness.yaml` at setup time.
- Larger file as platform grows — mitigated by clear section structure and schema validation.

## Scaling note

A single file becomes a merge-conflict hotspot when multiple contributors add apps or environments concurrently. Mitigation before that threshold is reached:

- Establish **section ownership conventions**: the `apps:` block is edited only via `extensions/{app}/app.yaml` source files; a CLI compile step (`harness compile`) merges them into `harness.yaml`. Other sections (keycloak, prometheus, caddy) remain hand-authored.
- Until the compile step is built, contributors must treat each top-level section as a separate ownership domain and avoid editing unrelated sections in the same commit.
