# Prometheus Integration

## Purpose

Collect and expose runtime metrics from harness-api using Prometheus.

## Owns

- metric collection
- metric storage (local)
- metric querying

## Does not own

- metric generation logic (owned by harness-api)
- alerting
- dashboards

## Approach

harness-api exposes a `GET /metrics` endpoint in Prometheus text format.

Prometheus runs as a Docker container and scrapes harness-api on a configured interval.

No custom ingest API is required.

## harness-api metrics endpoint

```text
GET http://harness-api:8000/metrics
```

Format: Prometheus text exposition format.

## Metric definitions

### Request counter

```text
harness_request_total{app, environment, route, variant, status_code}
```

### Request duration

```text
harness_request_duration_seconds{app, environment, route, variant}
```

Exposed as a histogram with buckets:

```text
0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5
```

## Prometheus config

Defined in `harness.yaml` under a `prometheus:` section.

Generates `infra/prometheus/prometheus.yml` via CLI:

```bash
harness generate-prometheus
```

## Port

```text
9090
```

## Non-goals

* Grafana dashboards
* alerting rules
* long-term metric retention
* production observability
