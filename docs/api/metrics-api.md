# Prometheus Scrape Reference

## Scrape endpoint

harness-api exposes metrics at:

```text
GET /metrics
```

Format: Prometheus text exposition format (`text/plain; version=0.0.4`).

## Example output

```text
# HELP harness_request_total Total requests handled by harness-api
# TYPE harness_request_total counter
harness_request_total{app="salesforce",environment="dev",route="account-detail",variant="unstable-selectors",status_code="200"} 42

# HELP harness_request_duration_seconds Request duration in seconds
# TYPE harness_request_duration_seconds histogram
harness_request_duration_seconds_bucket{app="salesforce",environment="dev",route="account-detail",variant="none",le="0.1"} 38
harness_request_duration_seconds_bucket{app="salesforce",environment="dev",route="account-detail",variant="none",le="0.25"} 41
harness_request_duration_seconds_sum{app="salesforce",environment="dev",route="account-detail",variant="none"} 3.82
harness_request_duration_seconds_count{app="salesforce",environment="dev",route="account-detail",variant="none"} 42
```

## Prometheus scrape config

```yaml
scrape_configs:
  - job_name: harness
    scrape_interval: 15s
    static_configs:
      - targets:
          - harness-api:8000
```

## Prometheus UI

```text
http://metrics.local
```

## Useful PromQL

Request rate by route:

```promql
rate(harness_request_total[5m])
```

Error rate:

```promql
rate(harness_request_total{status_code=~"5.."}[5m])
  / rate(harness_request_total[5m])
```

p95 latency by route:

```promql
histogram_quantile(0.95,
  rate(harness_request_duration_seconds_bucket[5m])
)
```
