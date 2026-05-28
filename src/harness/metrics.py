from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUEST_COUNTER = Counter(
    "harness_request_total",
    "Total requests handled by harness-api",
    ["app", "environment", "route", "variant", "status_code"],
)

REQUEST_DURATION = Histogram(
    "harness_request_duration_seconds",
    "Request duration in seconds",
    ["app", "environment", "route", "variant"],
    buckets=[0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)


def record_request(
    app_id: str,
    env_id: str,
    route_id: str,
    status_code: int,
    duration: float,
    variant: str = "none",
) -> None:
    REQUEST_COUNTER.labels(
        app=app_id,
        environment=env_id,
        route=route_id,
        variant=variant,
        status_code=str(status_code),
    ).inc()
    REQUEST_DURATION.labels(
        app=app_id,
        environment=env_id,
        route=route_id,
        variant=variant,
    ).observe(duration)


__all__ = ["record_request", "generate_latest", "CONTENT_TYPE_LATEST"]
