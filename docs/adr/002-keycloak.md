# ADR-002: Keycloak over a custom IdP implementation

## Status

Accepted

## Context

The platform needs a realistic OAuth 2.0 / OIDC identity provider to simulate enterprise authentication flows (Authorization Code, Client Credentials, token expiry, role claims). A custom implementation would need to cover the full OIDC spec and stay compliant over time.

## Decision

Use Keycloak (`quay.io/keycloak/keycloak`) running in Docker dev mode with a pre-configured realm imported from `infra/keycloak/harness-realm.json`.

## Consequences

- Full OIDC compliance out of the box — discovery endpoint, JWKS, token introspection.
- Realm configuration (users, roles, clients) is version-controlled as a JSON export.
- Keycloak adds ~500 MB to the Docker image set and increases cold-start time.
- No persistent storage required for local use; realm resets on container restart.

## Startup readiness gate

Reset-on-restart is only safe for auth-dependent automation if startup is deterministic and fast. The platform **must** enforce a readiness gate before any test or automation run proceeds:

1. Keycloak `/realms/harness/.well-known/openid-configuration` returns HTTP 200.
2. The `harness` realm exists and the expected clients are present (verified via Admin REST API or `harness idp verify`).
3. At least one test user can obtain a token via Client Credentials.

The developer CLI (`harness run`) must block until all three conditions pass or time out with a clear error. CI must call `harness idp verify` as a pre-test step. A failure here indicates a broken realm export, not a flaky test.
