# Service Boundaries

## Purpose

Define the network contracts between the four services that make up the local platform, including which ports are host-exposed and which are Docker-internal.

## Services

| Service | Technology | Port | Role |
|---|---|---|---|
| Caddy | Reverse proxy | 80 | Virtual-host routing, header injection, TLS termination |
| Harness | Python ASGI | 8000 | App mimics, URL routing, page rendering, metrics |
| Keycloak | Java, Docker | 8080 | OAuth 2.0 / OIDC: realm, tokens, sessions |
| Prometheus | Docker | 9090 | Metric scraping, storage, querying |

## Port exposure

| Service | Host-exposed | Docker-internal | Notes |
|---|---|---|---|
| Caddy | 80 | — | Entry point for all browser / UiPath traffic |
| Harness | no | 8000 | Caddy routes to Harness; direct access for local `uv run` dev |
| Keycloak | no | 8080 | Caddy proxies `/auth/*` to Keycloak; not reached directly from host |
| Prometheus | no | 9090 | Harness exposes `/metrics`; Prometheus scrapes internally |

In production-style Docker Compose deployments only port 80 (Caddy) is published to the host. All other inter-service traffic stays within the `harness-net` bridge network.

During local development (`uv run uvicorn ...`) Harness runs directly on the host at port 8000 without Docker.

## Communication paths

```text
Browser / UiPath
    │ HTTP :80
    ▼
Caddy
    │ HTTP :8000          Harness upstream per virtual host
    ▼
Harness
    │ HTTP :8080          Token validation (introspect / JWKS)
    ▼
Keycloak

Prometheus
    │ HTTP :8000/metrics  Scrape interval: 15 s
    ▼
Harness
```

## Trust boundary

Caddy is the trust boundary for the `X-Harness-*` header namespace.

Rules:

- Caddy **overwrites** any incoming `X-Harness-App`, `X-Harness-Env`, and `X-Harness-Host` headers before forwarding to Harness. Client-supplied values are discarded.
- Harness trusts `X-Harness-*` headers unconditionally when they arrive from Caddy.
- In development without Caddy the `Host` header is used directly; no `X-Harness-*` injection occurs.

This ensures that route resolution is always driven by Caddy's virtual-host configuration rather than by client-controlled headers.

## Keycloak token flow

Caddy enforces authentication by forwarding the `Authorization: Bearer` header to Keycloak's token introspection endpoint. The introspection result (`sub`, `roles`) is injected as `X-Harness-User` and `X-Harness-Roles` before the request reaches Harness.

Harness does not perform token validation; it consumes the injected headers passively.

## Prometheus metrics

Harness exposes a Prometheus-compatible `/metrics` endpoint. Labels:

| Label | Source |
|---|---|
| `app` | `RouteContext.app_id` |
| `environment` | `RouteContext.env_id` |
| `route` | `RouteContext.route_id` |
| `status_code` | HTTP response status |

Prometheus is configured in `harness.yaml` under the `prometheus:` key (scrape interval, optional target overrides).
