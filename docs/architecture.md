# Architecture

## Overview

The platform consists of independent services composed through a local environment layer.

```text
Browser / UiPath
    |
    v
Caddy
    |
    +------> Harness API
    |
    +------> Keycloak
    |
    +------> Prometheus
```

The architecture follows a service-oriented adapter pattern.

## Service responsibilities

### Harness API

Owns:

* enterprise application mimics
* URL contracts
* route resolution
* variants
* page rendering
* synthetic data
* metrics generation (exposes /metrics)

Does not own:

* OAuth/OIDC implementation
* authentication state management
* metrics storage

---

### Keycloak

Owns:

* login flow
* OAuth/OIDC endpoints
* tokens
* claims
* roles
* session behavior
* expiry behavior

Does not own:

* enterprise application behavior

Operated as:

* Docker container, dev mode
* pre-configured realm imported from `infra/keycloak/harness-realm.json`

---

### Prometheus

Owns:

* metric scraping
* metric storage (local)
* metric querying

Does not own:

* metric generation logic

Operated as:

* Docker container
* scrapes harness-api `/metrics` endpoint
* config generated from `harness.yaml`

---

### Caddy

Owns:

* host routing
* environment routing
* request headers
* HTTPS configuration
* service composition

Does not own:

* application behavior

---

### CLI

Owns:

* developer workflow
* initialization
* validation
* generation
* local execution commands
* realm export/import

Does not own:

* runtime behavior

## Package structure

```text
test-platform/

packages/
    core/
    cli/

services/
    harness-api/

infra/
    caddy/
    keycloak/
        harness-realm.json
    prometheus/
        prometheus.yml
    docker-compose.yml

config/
    harness.yaml
```

## Dependency rules

Allowed:

```text
CLI
    ↓

Harness API
    ↓

Core
```

Forbidden:

```text
Core → API
Core → CLI
Core → Caddy
```

## Extension model

Adding a new enterprise application should require only:

```text
extensions/<app>/
templates/<app>/
data/<app>/
config/harness.yaml  (add app entry)
```

No changes to core behavior should be required.

## Runtime behavior

Request flow:

1. Browser sends request
2. Caddy resolves host and environment
3. Request routed to harness-api
4. Variant information injected
5. harness-api processes request
6. Metrics recorded to /metrics endpoint
7. Prometheus scrapes metrics
8. Response returned

## Ports

```text
harness-api   8000
keycloak      8080
prometheus    9090
caddy         80 / 443
```

## Architectural principles

### Core owns contracts

Core defines system behavior.

### Extensions implement contracts

Enterprise mimics provide implementations.

### Adapters consume contracts

CLI, API, and future protocols interact through contracts.

### Services remain isolated

Services communicate through explicit interfaces only.
