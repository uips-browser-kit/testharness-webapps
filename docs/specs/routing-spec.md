# Routing Specification

## Purpose

Define how local hostnames and paths route to platform services.

## Owns

- host-to-service mapping
- environment routing
- Caddy generation inputs
- request forwarding rules

## Does not own

- page rendering
- OAuth/OIDC implementation
- app route semantics

## Runtime routing

```text
Browser / UiPath
    |
    v
Caddy
    |
    +--> harness-api
    +--> fake-idp
    +--> metrics-api
```

## Services

```text
harness-api   8000
fake-idp      8100
metrics-api   8200
caddy         80 / 443
```

## Host rules

```yaml
hosts:
  - host: sf-dev.local
    service: harness-api
    app: salesforce
    environment: dev

  - host: idp.local
    service: fake-idp

  - host: metrics.local
    service: metrics-api
```

## Caddy output

```caddyfile
sf-dev.local {
  reverse_proxy harness-api:8000
}

idp.local {
  reverse_proxy fake-idp:8100
}

metrics.local {
  reverse_proxy metrics-api:8200
}
```

## Header injection

Caddy may inject:

```text
X-Harness-Environment
X-Harness-App
X-Forwarded-Host
X-Request-Id
```

## Hosts file

```text
127.0.0.1 sf-dev.local
127.0.0.1 crm-dev.local
127.0.0.1 idp.local
127.0.0.1 metrics.local
```

## Validation

Reject:

```text
duplicate hosts
unknown services
unknown apps
unknown environments
invalid ports
missing hosts entries
```

## Non-goals

* defining application URL contracts
* implementing service logic
* managing production DNS
