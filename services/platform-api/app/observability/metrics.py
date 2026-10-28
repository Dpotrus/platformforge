from prometheus_client import Counter, Gauge, Histogram


HTTP_REQUESTS_TOTAL = Counter(
    "platformforge_http_requests_total",
    "Total number of HTTP requests handled by PlatformForge API.",
    labelnames=["method", "route", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "platformforge_http_request_duration_seconds",
    "Duration of HTTP requests in seconds.",
    labelnames=["method", "route"],
    buckets=(
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
    ),
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "platformforge_http_requests_in_progress",
    "Number of HTTP requests currently being processed.",
    labelnames=["method"],
)