# Contribution Guide

## Branch naming

Branches follow the pattern `{type}/{scope}-{short-description}`:

| Type | When to use |
|---|---|
| `feature/` | New functionality |
| `fix/` | Bug fix |
| `docs/` | Documentation only |
| `refactor/` | Code restructure without behaviour change |
| `test/` | Test additions or corrections |
| `chore/` | Tooling, dependencies, CI |

Examples:
```text
feature/challenge-catalog-api
fix/confluence-base-path-redirect
docs/update-cli-spec
```

Always branch from `development`. Never commit directly to `main` or `development`.

## Commit conventions

Commits use the Conventional Commits format:

```text
<type>(<scope>): <subject>

[optional body]
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.

Subject line: imperative mood, lowercase, no trailing period, under 72 characters.

Examples:
```text
feat(api): add Accept-header content negotiation
fix(renderer): prefix nav hrefs with base_path
docs(specs): write service-boundaries spec
test(cli): add view-data template-only assertions
```

Do not use emoji in commit messages.

## Running the test suite

```text
# Install dependencies
uv sync

# Fast suite (unit + fixture + integration, no live server)
uv run pytest -m "not integration" -q

# Full suite
uv run pytest -q

# Import boundary checks
uv run lint-imports

# Type checking
uv run mypy src/
```

All four must pass before a pull request is opened.

## Adding a new app

1. **harness.yaml** — add an entry under `apps:` with `id`, `vendor`, `product`, `environments`, `routes`, and `nav`.

2. **Seed data** — create `data/default/{app_id}/` and add one JSON file per `data_entity` declared on routes. Ensure the first record uses the ID from `SAMPLE_PARAMS`.

3. **Templates** — create `templates/{app_id}/` and add one Jinja2 template per route that has a `template:` key. Templates extend `layout` (defaults to `layouts/default.html`).

4. **CSS** — create `static/css/apps/{app_id}.css` overriding the 10 CSS variables from `static/css/base.css` with brand-accurate colours. See the CSS variable contract in `docs/specs/plugin-spec.md`.

5. **Tests** — add route-match fixture cases to `tests/fixtures/` and at least one integration test in `tests/test_router.py` or a new `tests/test_{app_id}.py`.

6. **Verify:**
   ```text
   uv run pytest -q
   uv run lint-imports
   ```

No changes to `src/core/` or `src/backend/` are required for a new app.

## Pull request policy

Do not open a pull request until a maintainer has confirmed scope on the relevant issue.

PR title: same format as the commit subject line.

PR description: include a summary of changes, a test plan checklist, and a link to the issue.

## Code style

The project uses `ruff` for linting and formatting. Run before committing:

```text
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

Type annotations are required on all public functions in `src/core/` and `src/backend/`.
