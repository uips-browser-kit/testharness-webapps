# ADR-003: Additive extension model — no core changes per app

## Status

Accepted

## Context

The platform must support 12+ enterprise app mimics with distinct URL patterns, data models, and page layouts. A monolithic approach (all apps in core) would make each addition a core code change, coupling unrelated apps and growing the core package indefinitely.

## Decision

Each enterprise app is an extension: a directory containing Jinja2 templates, optional Python hooks, and seed data. The Harness Extension Registry discovers extensions at startup. Core and Harness have no knowledge of specific apps.

Adding a new app requires only:
```
config/harness.yaml        ← app entry
extensions/{app}/          ← optional Python hooks
templates/{app}/           ← Jinja2 templates
data/default/{app}/        ← seed data
```

## Consequences

- Core and Harness remain unchanged when a new app is added.
- Extensions are independently testable.
- Discovery mechanism must be robust against malformed extensions.
- Extension interface must be stable — breaking changes to the extension API affect all apps.

## Interface versioning and deprecation policy

The extension interface is versioned starting at **v1**. The v1 contract covers:

- the directory layout (`extensions/{app}/`, `templates/{app}/`, `data/default/{app}/`)
- the Python hook entry points (callable signatures exposed to the Extension Registry)
- the template context variables injected by the Template Renderer

**Rules:**

- A breaking change to any v1 contract element requires a new major version (`v2`) and a minimum **one-release deprecation window** during which both versions are supported.
- Additive changes (new optional hook, new context variable) are non-breaking and do not require a version bump.
- The compatibility contract is enforced by a test suite that runs all registered extensions against the current interface. A new extension must pass these tests before merge.

Until a second extension is merged, the v1 interface is considered provisional and may be revised without a deprecation window.
