# ADR-004: uv workspace with parent venv

## Status

Accepted

## Context

`testharness-webapps` is a subproject within the `uips-browser-kit` monorepo. Python tooling needs to be consistent across the workspace. Without a shared venv, each subproject would manage its own environment independently, and packages installed in one would not be available to the other.

## Decision

Declare `testharness-webapps` as a virtual uv workspace member in the parent `pyproject.toml` (`[tool.uv.workspace] members = ["testharness-webapps"]`). All dependencies install into the single parent venv. `testharness-webapps/justfile` provides `just add` (`uv --directory .. add`) and `just run` (`uv run`) as developer shortcuts.

## Consequences

- One venv for the entire monorepo — no activation ceremony per subproject.
- `uv run` from `testharness-webapps/` resolves the parent venv automatically.
- `testharness-webapps/pyproject.toml` is a virtual member (no build artifact); dependencies are declared there for documentation but installed at the workspace level.
- A local `.venv` created accidentally inside the subproject must be removed; `.gitignore` excludes it.
