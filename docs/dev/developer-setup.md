# Developer Setup

## Purpose

Define how to run the test platform locally.

## Prerequisites

Required:

- Python 3.11+
- Docker
- Docker Compose
- editable hosts file access

## Repository shape

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

## Local hosts

The platform uses local hostnames to mimic enterprise environments.

Example:

```text
127.0.0.1 sf-dev.local
127.0.0.1 crm-dev.local
127.0.0.1 idp.local
127.0.0.1 metrics.local
```

## Services

```text
harness-api   → enterprise app mimics + /metrics endpoint
keycloak      → OAuth/OIDC simulation
prometheus    → metrics scraping and storage
caddy         → local routing fabric
```

## Ports

```text
harness-api   8000
keycloak      8080
prometheus    9090
caddy         80 / 443
```

## Docker startup

Start the platform:

```bash
docker compose -f infra/docker-compose.yml up --build
```

Stop the platform:

```bash
docker compose -f infra/docker-compose.yml down
```

## Python setup

Create virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install packages:

```bash
pip install -e packages/core
pip install -e packages/cli
```

## CLI checks

Validate config:

```bash
harness validate
```

Generate Caddy config:

```bash
harness generate-caddy
```

Generate Prometheus config:

```bash
harness generate-prometheus
```

Export Keycloak realm:

```bash
harness idp export
```

Import Keycloak realm:

```bash
harness idp import
```

Seed data:

```bash
harness seed
```

Run local platform:

```bash
harness run
```

## Expected URLs

```text
http://sf-dev.local          → Salesforce mimic (dev)
http://crm-dev.local         → Dynamics mimic (dev)
http://idp.local             → Keycloak login
http://idp.local/admin       → Keycloak admin console
http://metrics.local         → Prometheus UI
```

## Startup flow

```text
1. Edit hosts file
2. Install Python packages
3. Validate config (harness validate)
4. Generate Caddy config (harness generate-caddy)
5. Generate Prometheus config (harness generate-prometheus)
6. Export realm (harness idp export)
7. Start Docker Compose
8. Open enterprise mimic URL
```

## Validation

A local setup is valid when:

* Docker services start successfully
* Caddy routes hostnames correctly
* harness-api renders enterprise pages
* Keycloak serves OIDC discovery at `http://idp.local/realms/harness/.well-known/openid-configuration`
* Keycloak admin console is reachable at `http://idp.local/admin`
* Prometheus targets page shows harness-api as UP at `http://metrics.local/targets`
* CLI validates configuration successfully

## Non-goals

This document does not define:

* enterprise app behavior
* URL contract rules
* variant behavior
* Keycloak realm configuration details
* Prometheus metric definitions
