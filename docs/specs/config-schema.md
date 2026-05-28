# harness.yaml Schema

## Purpose

Single configuration file for the local test platform.

Replaces the previous five-file layout (`apps.yaml`, `routes.yaml`, `environments.yaml`, `variants.yaml`, `idp.yaml`).

## Top-level sections

```text
apps
variants
keycloak
prometheus
caddy
```

## Complete example

```yaml
apps:

  - id: salesforce
    vendor: Salesforce
    product: Lightning
    enabled: true
    templates: templates/salesforce
    data: data/default/salesforce

    environments:

      dev:
        host: sf-dev.local
        base_path: /

      test:
        host: sf-test.local
        base_path: /sf

    routes:

      - id: account-detail
        path: /lightning/r/Account/{id}/view
        methods:
          - GET
        page: account-page
        parameters:
          id:
            type: string
            required: true

      - id: dashboard
        path: /lightning/page/home
        methods:
          - GET
        page: dashboard-page

    pages:

      account-page:
        template: account.html
        layout: default

      dashboard-page:
        template: dashboard.html
        layout: dashboard

    variants:
      - unstable-selectors
      - latency-500

variants:

  - id: unstable-selectors
    group: selector
    enabled: true
    scope:
      apps:
        - salesforce

  - id: latency-500
    group: latency
    enabled: true
    scope:
      apps:
        - salesforce

keycloak:

  realm: harness
  base_url: http://idp.local

  clients:

    - id: browser-client
      flow: authorization_code
      redirect_uris:
        - http://sf-dev.local/*

    - id: service-client
      flow: client_credentials

  users:

    - id: user-001
      email: admin@example.local
      password: admin
      roles:
        - admin

    - id: user-002
      email: readonly@example.local
      password: readonly
      roles:
        - viewer

prometheus:

  scrape_interval: 15s

caddy:

  tls: false
```

## apps section

Required per app:

```text
id
vendor
product
enabled
templates
data
environments (at least one)
routes (at least one)
```

Required per environment:

```text
host
base_path
```

Required per route:

```text
id
path
methods
page
```

## variants section

Required:

```text
id
group
enabled
scope.apps
```

## keycloak section

Required:

```text
realm
base_url
users
```

## prometheus section

Optional. Default scrape interval: `15s`.

## caddy section

Optional. If omitted, Caddy config is fully generated from `apps`.

## Validation rules

Reject:

```text
duplicate app ids
duplicate route ids within an app
unknown page references
unknown variant references
missing template directories
missing data directories
invalid path parameters (unclosed braces)
```
