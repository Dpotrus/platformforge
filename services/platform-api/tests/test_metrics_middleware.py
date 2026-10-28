from fastapi.testclient import TestClient

from app.main import app
from app.observability.metrics import (
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_IN_PROGRESS,
)

def get_histogram_count(histogram) -> float:
    for sample in histogram.collect()[0].samples:
        if sample.name.endswith("_count"):
            return sample.value

    raise AssertionError("Histogram count sample not found")


def test_health_request_records_metrics() -> None:
    method = "GET"
    route = "/health"
    status_code = "200"

    counter = HTTP_REQUESTS_TOTAL.labels(
        method=method,
        route=route,
        status_code=status_code,
    )

    histogram = HTTP_REQUEST_DURATION_SECONDS.labels(
        method=method,
        route=route,
    )

    gauge = HTTP_REQUESTS_IN_PROGRESS.labels(
        method=method,
    )

    counter_before = counter._value.get()
    histogram_before = get_histogram_count(histogram)
    gauge_before = gauge._value.get()

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200

    assert counter._value.get() == counter_before + 1
    assert get_histogram_count(histogram) == histogram_before + 1
    assert gauge._value.get() == gauge_before


def test_unknown_route_uses_unmatched_label() -> None:
    counter = HTTP_REQUESTS_TOTAL.labels(
        method="GET",
        route="unmatched",
        status_code="404",
    )

    counter_before = counter._value.get()

    with TestClient(app) as client:
        response = client.get("/this-route-does-not-exist")

    assert response.status_code == 404
    assert counter._value.get() == counter_before + 1

def test_post_request_records_metrics() -> None:
    counter = HTTP_REQUESTS_TOTAL.labels(
        method="POST",
        route="/api/v1/applications/",
        status_code="422",
    )

    before = counter._value.get()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/applications/",
            json={},
        )

    assert response.status_code == 422
    assert counter._value.get() == before + 1

def test_redirect_records_307_status() -> None:
    counter = HTTP_REQUESTS_TOTAL.labels(
        method="POST",
        route="unmatched",
        status_code="307",
    )

    before = counter._value.get()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/applications",
            json={},
            follow_redirects=False,
        )

    assert response.status_code == 307
    assert counter._value.get() == before + 1