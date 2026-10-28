from fastapi.testclient import TestClient

from app.main import app
from app.observability.metrics import HTTP_REQUESTS_TOTAL


def test_metrics_endpoint_returns_prometheus_format() -> None:
    with TestClient(app) as client:
        client.get("/health")
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]

    assert "platformforge_http_requests_total" in response.text
    assert "platformforge_http_request_duration_seconds" in response.text
    assert "platformforge_http_requests_in_progress" in response.text


def test_metrics_endpoint_does_not_record_itself() -> None:
    counter = HTTP_REQUESTS_TOTAL.labels(
        method="GET",
        route="/metrics",
        status_code="200",
    )

    before = counter._value.get()

    with TestClient(app) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert counter._value.get() == before


def test_metrics_endpoint_is_not_in_openapi_schema() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/metrics" not in response.json()["paths"]