# PlatformForge Local Observability

This directory contains the local observability environment for PlatformForge.

It provides:

- **Prometheus** for application metrics collection.
- **OpenTelemetry Collector** for receiving and processing distributed traces.
- **Grafana Tempo** for storing and querying distributed traces.
- **Grafana** for visualizing metrics and exploring traces.
- **Docker Compose** for managing the local observability infrastructure.

The environment is intended for local development, testing and learning.

For the Kubernetes observability environment, see `infrastructure/observability/README.md`.

## Architecture

PlatformForge supports two observability signals:

1. **Metrics** — aggregated measurements of application behavior.
2. **Distributed traces** — detailed information about individual requests and their database operations.

### Metrics Architecture

The PlatformForge API exposes Prometheus metrics at `/metrics`.

Prometheus scrapes the API through `host.docker.internal:8000`.

```text
PlatformForge API
localhost:8000
      |
      | /metrics
      v
Prometheus
localhost:9090
      |
      | PromQL
      v
Grafana
localhost:3000
```

Metrics provide information about HTTP request rates, error rates, latency and concurrent requests.

### Distributed Tracing Architecture

PlatformForge uses OpenTelemetry to instrument FastAPI and SQLAlchemy.

FastAPI instrumentation creates server spans for incoming HTTP requests.

SQLAlchemy instrumentation creates client spans for database operations.

Traces are exported using OTLP over HTTP.

```text
PlatformForge API
  |
  | FastAPI SERVER spans
  | SQLAlchemy CLIENT spans
  |
  | OTLP HTTP :4318
  v
OpenTelemetry Collector
  |
  | Memory Limiter
  | Batch Processor
  |
  | OTLP HTTP :4318
  v
Grafana Tempo
  |
  | Trace queries
  v
Grafana Explore
localhost:3000
```

The API exports traces to OpenTelemetry Collector rather than directly to Tempo.

This separates application instrumentation from the tracing backend.

The Collector can receive traces through both OTLP HTTP and OTLP gRPC.

The current PlatformForge API uses OTLP HTTP.

### Docker Networking

The PlatformForge API and observability infrastructure are managed by separate Docker Compose projects.

The main Compose project creates the Docker network:

```text
platformforge_default
```

The OpenTelemetry Collector connects to both:

- The observability Compose project's default network.
- The external `platformforge_default` network.

This allows the API to reach the Collector using Docker DNS:

```text
http://otel-collector:4318
```

The Collector communicates with Tempo through the observability network:

```text
http://tempo:4318
```

The main application stack should be started before the observability stack when setting up the environment for the first time.

## Directory Structure

```text
observability/
├── README.md
├── compose.yml
├── collector/
│   └── config.yaml
├── tempo/
│   └── config.yaml
├── prometheus/
│   └── prometheus.yml
└── grafana/
    └── provisioning/
        ├── datasources/
        │   └── tempo.yml
        └── dashboards/
            └── json/
                └── platformforge-api.json
```

The Grafana provisioning directory also contains the existing Prometheus datasource configuration.

The dashboard JSON is shared with the Kubernetes observability environment.

## Prerequisites

The verified local environment uses:

- Windows with PowerShell 7
- Docker Desktop with Linux containers
- Docker Compose
- Python 3.13
- PlatformForge API
- PostgreSQL 17

Commands are intended to run from the repository root unless otherwise specified.

The main application stack requires a configured `DATABASE_URL` environment variable.

The observability stack requires the external Docker network `platformforge_default`.

## 1. Start the PlatformForge Application

Start the main application stack:

```powershell
docker compose up -d
```

This starts the PlatformForge API and PostgreSQL.

Verify the containers:

```powershell
docker compose ps
```

The API should be accessible on port `8000`.

Verify the health endpoint:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Verify that Prometheus metrics are available:

```powershell
Invoke-WebRequest http://localhost:8000/metrics
```

The API must be running before Prometheus can successfully scrape its metrics.

Starting the main stack also ensures that the `platformforge_default` Docker network exists.

## 2. Start the Observability Environment

Start Prometheus, Grafana, OpenTelemetry Collector and Tempo:

```powershell
docker compose -f .\observability\compose.yml up -d
```

Verify the containers:

```powershell
docker compose -f .\observability\compose.yml ps
```

The following services should be running:

| Service | Local port | Purpose |
|---|---|---|
| Prometheus | 9090 | Metrics collection and queries |
| Grafana | 3000 | Metrics dashboards and trace exploration |
| OpenTelemetry Collector | 4317 | OTLP gRPC receiver |
| OpenTelemetry Collector | 4318 | OTLP HTTP receiver |
| OpenTelemetry Collector | 13133 | Collector health endpoint |
| Grafana Tempo | 3200 | Tempo HTTP API |

The OpenTelemetry Collector and Tempo run separately from the PlatformForge API.

## 3. Verify Prometheus

Open Prometheus:

```text
http://localhost:9090
```

Navigate to:

**Status → Target health**

Verify that the PlatformForge API target is UP.

The Prometheus configuration is located at:

```text
observability/prometheus/prometheus.yml
```

Example PromQL query:

```promql
platformforge_http_requests_total
```

The API also exposes request-duration and in-progress request metrics.

## 4. Verify Grafana Metrics

Open Grafana:

```text
http://localhost:3000
```

Grafana automatically provisions its Prometheus datasource and PlatformForge dashboard.

The Prometheus datasource UID is:

```text
prometheus
```

Locate the dashboard:

**PlatformForge API**

Dashboard UID:

```text
platformforge-api
```

The dashboard contains four panels:

1. HTTP Request Rate
2. HTTP 5xx Error Rate
3. HTTP P95 Latency
4. HTTP Requests In Progress

### Generate Metrics Traffic

Generate HTTP requests against the API:

```powershell
1..50 | ForEach-Object {
    Invoke-RestMethod http://localhost:8000/health | Out-Null
    Start-Sleep -Milliseconds 100
}
```

Wait for the next Prometheus scrape and refresh the Grafana dashboard.

The HTTP Request Rate and HTTP P95 Latency panels should show activity.

The HTTP 5xx Error Rate panel may show zero when no server errors occur.

## 5. OpenTelemetry Configuration

The PlatformForge API uses environment variables to configure distributed tracing.

The main `compose.yml` contains:

```yaml
OTEL_TRACING_ENABLED: "true"
OTEL_SERVICE_NAME: platformforge-api
OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4318
```

| Environment variable | Purpose |
|---|---|
| `OTEL_TRACING_ENABLED` | Enables application tracing |
| `OTEL_SERVICE_NAME` | Identifies the service in traces |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Configures the Collector endpoint |

`OTEL_TRACING_ENABLED` is an application-specific configuration setting.

When tracing is enabled, the application creates an OpenTelemetry tracer provider and instruments FastAPI and SQLAlchemy.

The application exports spans using the OTLP HTTP exporter.

The configured endpoint is extended with `/v1/traces` when constructing the exporter.

The resulting endpoint is:

```text
http://otel-collector:4318/v1/traces
```

### SQLAlchemy Compatibility

The application currently uses SQLAlchemy 2.0.x.

The dependency is constrained in `services/platform-api/pyproject.toml`:

```toml
"sqlalchemy>=2.0,<2.1"
```

This constraint maintains compatibility with the OpenTelemetry SQLAlchemy instrumentation version used by PlatformForge.

The dependency constraint should be reviewed when upgrading OpenTelemetry instrumentation or SQLAlchemy.

## 6. OpenTelemetry Collector

The Collector configuration is stored in:

```text
observability/collector/config.yaml
```

The Collector receives traces through OTLP HTTP or OTLP gRPC.

The configured tracing pipeline is:

```text
OTLP Receiver
      |
      v
Memory Limiter
      |
      v
Batch Processor
      |
      v
OTLP HTTP Exporter
      |
      v
Grafana Tempo
```

### Memory Limiter

The memory limiter helps protect the Collector against excessive memory usage.

The local configuration uses:

```yaml
check_interval: 5s
limit_mib: 256
```

### Batch Processor

The batch processor groups spans before exporting them.

The local configuration uses:

```yaml
timeout: 5s
send_batch_size: 512
```

This reduces the number of export requests.

Because spans are processed in batches, a short delay may occur before new traces appear in Grafana.

### Tempo Exporter

The Collector exports traces to:

```text
http://tempo:4318
```

The OTLP HTTP exporter sends trace data to the corresponding `/v1/traces` endpoint.

### Health Endpoint

The Collector exposes a health endpoint on port `13133`.

The health extension is enabled in the Collector service configuration.

## 7. Grafana Tempo

Tempo stores and serves distributed traces.

The Tempo configuration is stored in:

```text
observability/tempo/config.yaml
```

The local deployment uses:

- OTLP HTTP receiver on port `4318`.
- OTLP gRPC receiver on port `4317`.
- HTTP API on port `3200`.
- Local trace storage.
- Docker volume persistence.

### Trace Storage

Tempo uses the local storage backend:

```yaml
storage:
  trace:
    backend: local

    wal:
      path: /var/tempo/wal

    local:
      path: /var/tempo/blocks
```

The Docker Compose configuration mounts a persistent volume:

```yaml
tempo_data:/var/tempo
```

This allows stored trace data to survive container recreation, provided the Docker volume is retained.

Trace retention is not explicitly configured in the current local configuration.

The effective retention behavior depends on the Tempo version and its defaults.

For production-like environments, retention should be configured explicitly.

## 8. Verify Distributed Tracing

Distributed tracing has been verified end-to-end using the PlatformForge API, PostgreSQL, OpenTelemetry Collector, Tempo and Grafana.

### Step 1: Generate an API Request

Execute:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/applications/
```

This endpoint retrieves applications from PostgreSQL.

The request should produce:

- A FastAPI server span.
- SQLAlchemy client spans for database operations.

### Step 2: Open Grafana Explore

Open Grafana:

```text
http://localhost:3000
```

Navigate to:

**Explore**

Select the Tempo datasource.

Search for traces from the service:

```text
platformforge-api
```

Use a recent time range that includes the API request.

### Step 3: Inspect the Trace

Open a trace corresponding to:

```text
GET /api/v1/applications/
```

The trace should contain a server span representing the HTTP request.

Within the same trace, SQLAlchemy client spans should represent database activity.

A verified PlatformForge trace contained:

```text
GET /api/v1/applications/    SERVER
    |
    +-- connect              CLIENT
    |
    +-- SELECT platformforge CLIENT
```

The exact span names and number of spans may vary depending on instrumentation and database connection behavior.

### Step 4: Verify Database Attributes

Inspect the SQLAlchemy query span.

The verified PostgreSQL trace included attributes such as:

```text
db.system = postgresql
db.name = platformforge
net.peer.name = postgres
net.peer.port = 5432
```

The query span also included a `db.statement` attribute containing the SQL query.

### Step 5: Verify Parent-Child Relationships

Confirm that the SQLAlchemy client spans belong to the same trace as the FastAPI server span.

This demonstrates that the tracing context propagates from the incoming HTTP request to database operations.

The expected relationship is:

```text
HTTP Request
    |
    v
FastAPI SERVER Span
    |
    v
SQLAlchemy CLIENT Span
    |
    v
PostgreSQL
```

The verified implementation successfully produced this relationship.

## 9. Tracing Lifecycle

PlatformForge manages tracing through the FastAPI application lifecycle.

The tracing implementation is located in:

```text
services/platform-api/app/observability/tracing.py
```

The application lifecycle integration is located in:

```text
services/platform-api/app/main.py
```

The implementation manages:

- Tracer provider creation.
- FastAPI instrumentation.
- SQLAlchemy instrumentation.
- SQLAlchemy instrumentation ownership.
- Database resource lifecycle.
- Instrumentation cleanup.
- Tracer provider shutdown.
- Failure handling during startup and shutdown.

SQLAlchemy instrumentation is process-wide and requires controlled ownership.

PlatformForge prevents conflicting instrumentation ownership and handles cleanup failures explicitly.

The application also avoids unnecessary SQLAlchemy instrumentation when tracing is disabled.

These behaviors are covered by automated tests.

## 10. Automated Tests

The tracing implementation includes unit tests and integration tests.

Relevant test files include:

```text
services/platform-api/tests/test_tracing.py
services/platform-api/tests/test_app_factory_tracing.py
services/platform-api/tests/test_lifespan.py
services/platform-api/tests/test_db_session.py
```

The tests cover:

- Tracer provider configuration.
- FastAPI instrumentation.
- SQLAlchemy instrumentation ownership.
- Instrumentation lifecycle.
- Startup and shutdown cleanup.
- Failure handling and recovery.
- Database resource disposal.
- Application factory isolation.
- Real SQLAlchemy instrumentation.

### Real SQLAlchemy Instrumentation Test

The tracing test suite includes a subprocess-based integration test using:

- A real SQLAlchemy engine.
- An in-memory SQLite database.
- A real OpenTelemetry tracer provider.
- An in-memory span exporter.
- A parent span surrounding a SQL query.

The test verifies that SQLAlchemy instrumentation creates a client span with database attributes and the expected parent-child relationship.

Running the test in a separate process isolates process-wide instrumentation state from the rest of the test suite.

### Run the Test Suite

From the PlatformForge API directory:

```powershell
cd .\services\platform-api
python -m pytest
```

The completed tracing implementation was verified with:

```text
197 passed
```

This result was obtained after aligning the SQLAlchemy dependency with the supported OpenTelemetry instrumentation version.

## 11. Dashboard as Code

The dashboard definition is stored in:

```text
observability/grafana/provisioning/dashboards/json/platformforge-api.json
```

This file is the single source of truth for the PlatformForge API dashboard.

Docker Compose uses the JSON through Grafana provisioning.

The Kubernetes environment uses the same JSON file through a labeled ConfigMap and Grafana's dashboard sidecar.

To provision the dashboard in Kubernetes, run:

```powershell
.\infrastructure\scripts\install-observability-dashboard.ps1 `
    -KubeContext kind-platformforge-observability
```

No separate Kubernetes dashboard JSON is maintained.

## 12. Stop the Observability Environment

Stop the observability containers:

```powershell
docker compose -f .\observability\compose.yml down
```

This stops and removes the observability containers and their Compose network.

The external `platformforge_default` network is managed by the main application Compose project.

**Do not use `down -v` during routine operations.**

Removing volumes can destroy stored Prometheus, Grafana and Tempo data.

The PlatformForge API and PostgreSQL are managed separately from the observability Compose project.

To stop the main application stack:

```powershell
docker compose down
```

Avoid removing PostgreSQL volumes unless intentionally resetting the local database.

## Troubleshooting

### Prometheus Target Is DOWN

Verify that the PlatformForge API is running:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Check the Prometheus target status and confirm that its scrape configuration uses the correct address.

### Grafana Shows No Metrics

Verify that:

- The API is running.
- Prometheus can scrape `/metrics`.
- The Prometheus datasource is available.
- The dashboard uses datasource UID `prometheus`.
- The selected Grafana time range includes recent traffic.

### OpenTelemetry Collector Cannot Start

Verify that the main PlatformForge Compose project is running:

```powershell
docker compose ps
```

Verify that the shared Docker network exists:

```powershell
docker network inspect platformforge_default
```

Check the Collector logs:

```powershell
docker compose -f .\observability\compose.yml logs otel-collector
```

### No Traces in Grafana

Verify that:

- The PlatformForge API is running.
- Tracing is enabled in the API configuration.
- The Collector is running.
- Tempo is running.
- The Tempo datasource is available in Grafana.
- The selected time range includes recent API requests.

Generate a request:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/applications/
```

Wait a few seconds for spans to be exported and processed.

Check the Collector logs:

```powershell
docker compose -f .\observability\compose.yml logs otel-collector
```

Check the Tempo logs:

```powershell
docker compose -f .\observability\compose.yml logs tempo
```

Check the API logs:

```powershell
docker compose logs api
```

### SQLAlchemy Instrumentation Problems

Verify the installed SQLAlchemy version:

```powershell
python -m pip show sqlalchemy
```

Verify the installed instrumentation version:

```powershell
python -m pip show opentelemetry-instrumentation-sqlalchemy
```

Check dependency compatibility:

```powershell
python -m pip check
```

The current PlatformForge dependency constraint requires SQLAlchemy 2.0.x.

### Port Conflicts

The local environment uses:

| Service | Port |
|---|---|
| PlatformForge API | 8000 |
| PostgreSQL | 5432 |
| Prometheus | 9090 |
| Grafana | 3000 |
| OpenTelemetry Collector gRPC | 4317 |
| OpenTelemetry Collector HTTP | 4318 |
| OpenTelemetry Collector health | 13133 |
| Grafana Tempo | 3200 |

The Kubernetes observability environment uses separate local port-forward ports:

| Service | Port |
|---|---|
| Kubernetes Prometheus | 9091 |
| Kubernetes Grafana | 3001 |

This allows both observability environments to be accessed without conflicts on those Grafana and Prometheus ports.

## Current Status

The following functionality has been implemented and verified:

### Metrics

- Prometheus HTTP metrics in FastAPI.
- Docker Compose monitoring environment.
- Prometheus scraping the PlatformForge API.
- Grafana Prometheus datasource provisioning.
- PlatformForge API dashboard provisioning.
- Four working dashboard panels.
- Shared dashboard JSON between Docker Compose and Kubernetes.

### Distributed Tracing

- OpenTelemetry SDK integration.
- FastAPI server span instrumentation.
- SQLAlchemy client span instrumentation.
- OpenTelemetry Collector deployment.
- OTLP HTTP trace export.
- Grafana Tempo deployment.
- Grafana Tempo datasource provisioning.
- PostgreSQL database spans.
- Parent-child relationships between HTTP and database spans.
- SQLAlchemy instrumentation lifecycle management.
- Startup and shutdown failure handling.
- Automated instrumentation tests.
- End-to-end verification in Grafana Explore.

### Verification

The completed implementation has been verified through:

- Automated Python tests: **197 passed**.
- Running Docker Compose infrastructure.
- Successful API requests against PostgreSQL.
- Real SQLAlchemy instrumentation integration testing.
- Distributed traces visible in Grafana Tempo.
- Verified FastAPI SERVER and PostgreSQL CLIENT spans within the same trace.

### Future Improvements

Potential future improvements include:

- Distributed tracing in Kubernetes.
- Centralized application logging.
- Correlation between logs and traces.
- Alerting.
- Explicit trace retention policies.
- More advanced Collector monitoring.
- Production-oriented resource limits and healthchecks.
- Trace sampling strategies.