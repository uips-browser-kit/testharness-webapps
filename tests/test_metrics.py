import pytest
from fastapi.testclient import TestClient

from src.api.app import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _metrics_text(client) -> str:
    return client.get("/metrics").text


# --- /metrics endpoint --------------------------------------------------------


def test_metrics_endpoint_ok(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]


def test_metrics_contains_counter_definition(client):
    assert "harness_request_total" in _metrics_text(client)


def test_metrics_contains_histogram_definition(client):
    assert "harness_request_duration_seconds" in _metrics_text(client)


# --- label emission per status code -------------------------------------------


def test_200_label_emitted(client):
    client.get("/lightning/r/Account/001/view", headers={"host": "sf-dev.local"})
    text = _metrics_text(client)
    assert 'status_code="200"' in text
    assert 'app="salesforce"' in text
    assert 'environment="dev"' in text
    assert 'route="account-detail"' in text


def test_404_label_emitted(client):
    client.get("/no/match/here", headers={"host": "sf-dev.local"})
    text = _metrics_text(client)
    assert 'status_code="404"' in text


def test_duration_histogram_observed(client):
    client.get("/lightning/r/Account/001/view", headers={"host": "sf-dev.local"})
    text = _metrics_text(client)
    assert "harness_request_duration_seconds_bucket" in text
    assert "harness_request_duration_seconds_sum" in text


# --- /health is excluded from metrics -----------------------------------------


def test_health_not_in_route_labels(client):
    client.get("/health")
    text = _metrics_text(client)
    assert 'route="health"' not in text
