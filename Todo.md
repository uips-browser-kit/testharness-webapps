# TODO

## Open

- [ ] Fill empty file: `docs/specs/plugin-spec.md`
- [ ] Fill empty file: `docs/specs/service-boundaries.md`
- [ ] Fill empty file: `docs/dev/contribution-guide.md`
- [ ] Fill empty file: `docs/dev/testing-strategy.md`

---

## Session summary

Created docs structure and initial specs, then corrected architecture from a GPT-generated draft: replaced custom fake-idp and metrics-api services with Keycloak and Prometheus, consolidated five config files into a single `harness.yaml`, deleted the redundant url-contract spec, and aligned all references consistently across the doc set.

### Created

- `.gitignore` — ignores `tmp/`
- `docs/vision.md`
- `docs/architecture.md`
- `docs/app-profile-catalog.md`
- `docs/specs/app-profile-spec.md`
- `docs/specs/variant-model.md`
- `docs/specs/routing-spec.md`
- `docs/specs/fake-idp-spec.md`
- `docs/specs/metrics-spec.md`
- `docs/specs/config-schema.md`
- `docs/specs/cli-spec.md`
- `docs/specs/data-generation-spec.md`
- `docs/specs/service-boundaries.md` *(empty)*
- `docs/specs/plugin-spec.md` *(empty)*
- `docs/api/harness-api.md`
- `docs/api/fake-idp-api.md`
- `docs/api/metrics-api.md`
- `docs/dev/developer-setup.md`
- `docs/dev/testing-strategy.md` *(empty)*
- `docs/dev/contribution-guide.md` *(empty)*

### Deleted

- `docs/specs/url-contract.md` — redundant with `app-profile-spec.md`; URL resolution section absorbed into `app-profile-spec.md`

### Updated

- `docs/architecture.md` — Keycloak replaces Fake IdP, Prometheus replaces Metrics API; ports, package structure, config file list
- `docs/specs/app-profile-spec.md` — added URL resolution section (input → processing → output)
- `docs/specs/routing-spec.md` — corrected service names and ports to keycloak:8080, prometheus:9090
- `docs/specs/fake-idp-spec.md` — rewritten as Keycloak integration spec
- `docs/specs/metrics-spec.md` — rewritten as Prometheus integration spec
- `docs/specs/config-schema.md` — rewritten as single `harness.yaml` schema
- `docs/api/fake-idp-api.md` — rewritten as Keycloak OIDC endpoint reference
- `docs/api/metrics-api.md` — rewritten as Prometheus scrape reference
- `docs/dev/developer-setup.md` — updated services, ports, CLI commands, validation steps
- `tmp/implementation-plan.md` — milestones updated: workspace layout, harness.yaml config, Keycloak milestone, Prometheus milestone, CLI commands, Docker Compose services
