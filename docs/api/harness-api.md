# Harness API

## Purpose

Expose enterprise application mimics over HTTP.

## Owns

- app page rendering
- route matching
- variant application
- synthetic data access
- request metrics emission

## Does not own

- OAuth/OIDC
- token issuance
- Caddy routing
- metrics storage

## Endpoints

### Health

```http
GET /health
```

Response:

```json
{ "status": "ok" }
```

### Render app route

```http
GET /{app}/{route}
```

Used for internal/direct testing. Normal traffic should arrive through Caddy host routing.

### Resolve URL

```http
POST /resolve
```

Request:

```json
{
  "app": "salesforce",
  "environment": "dev",
  "route": "account-detail",
  "parameters": {
    "id": "001"
  },
  "query": {}
}
```

Response:

```json
{
  "url": "http://sf-dev.local/lightning/r/Account/001/view"
}
```

### Match request

```http
POST /match
```

Request:

```json
{
  "host": "sf-dev.local",
  "path": "/lightning/r/Account/001/view",
  "method": "GET"
}
```

Response:

```json
{
  "app": "salesforce",
  "environment": "dev",
  "route": "account-detail",
  "parameters": {
    "id": "001"
  }
}
```

## Headers

```text
X-Harness-Variant
X-Harness-Seed
X-Harness-Environment
X-Request-Id
```

## Error codes

```text
400 invalid request
404 route not found
409 incompatible variants
500 render error
```
