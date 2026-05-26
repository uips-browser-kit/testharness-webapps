# Keycloak Integration

## Purpose

Provide OAuth/OIDC identity simulation for local testing using Keycloak.

## Owns

- realm configuration
- user and role definitions
- token issuance
- session behavior
- token expiry

## Does not own

- enterprise app rendering
- URL contracts
- page variants
- production identity management

## Approach

Keycloak runs as a Docker container using the `quay.io/keycloak/keycloak` image in development mode.

A pre-configured realm (`harness`) is imported on startup from a realm export file at:

```text
infra/keycloak/harness-realm.json
```

No persistent storage is required for local use. The realm resets on container restart.

## Realm

Realm name: `harness`

Defines:

- clients (browser automation client, service client)
- users
- roles
- token expiry
- session settings

## OIDC discovery

```text
http://idp.local/realms/harness/.well-known/openid-configuration
```

## Token validation

harness-api validates tokens using Keycloak's JWKS endpoint:

```text
http://idp.local/realms/harness/protocol/openid-connect/certs
```

## Auth flows

Browser automation:

```text
Authorization Code Flow
```

Service-to-service (CLI, internal):

```text
Client Credentials Flow
```

## Config source

Users and roles are defined in `harness.yaml` under a `keycloak:` section.

The CLI generates the realm export JSON from this config:

```bash
harness idp export
```

To import a realm export into a running Keycloak:

```bash
harness idp import
```

## Port

```text
8080
```

## Non-goals

* production identity management
* multi-tenant realms
* LDAP/AD integration
* custom identity provider bridging
