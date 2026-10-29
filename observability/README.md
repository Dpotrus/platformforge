# PlatformForge Local Observability

This directory contains the local observability environment for PlatformForge.

It provides Prometheus metrics collection and Grafana dashboards using Docker Compose.

The environment is intended for local development, testing and learning.

For the Kubernetes observability environment, see `infrastructure/observability/README.md`.

## Architecture

The local observability environment consists of:

- **PlatformForge API** running locally on port `8000`.
- **Prometheus** collecting application metrics.
- **Grafana** visualizing application metrics.
- **Docker Compose** managing the monitoring containers.

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

The monitoring containers run separately from the PlatformForge API.

## Directory Structure

```text
observability/
├── README.md
├── compose.yml
├── prometheus/
│   └── prometheus.yml
└── grafana/
    └── provisioning/
        ├── datasources/
        └── dashboards/
            └── json/
                └── platformforge-api.json
```

The dashboard JSON is shared with the Kubernetes observability environment.

## Prerequisites

The verified local environment uses:

- Windows with PowerShell 7
- Docker Desktop with Linux containers
- Docker Compose
- PlatformForge API running locally

Commands are intended to run from the repository root.

## 1. Start the PlatformForge API

The PlatformForge API must be running and accessible on port `8000`.

The API exposes:

```text
http://localhost:8000/health
http://localhost:8000/metrics
```

Verify the health endpoint:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Verify that metrics are available:

```powershell
Invoke-WebRequest http://localhost:8000/metrics
```

The API must be running before Prometheus can successfully scrape its metrics.

## 2. Start Prometheus and Grafana

Start the monitoring containers:

```powershell
docker compose -f .\observability\compose.yml up -d
```

Verify the containers:

```powershell
docker compose -f .\observability\compose.yml ps
```

Both Prometheus and Grafana should be running.

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

## 4. Verify Grafana

Open Grafana:

```text
http://localhost:3000
```

Grafana automatically provisions its Prometheus datasource and PlatformForge dashboard.

The datasource UID is:

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

## 5. Generate Test Traffic

Generate HTTP requests against the local API:

```powershell
1..50 | ForEach-Object {
    Invoke-RestMethod http://localhost:8000/health | Out-Null
    Start-Sleep -Milliseconds 100
}
```

Wait for the next Prometheus scrape and refresh the Grafana dashboard.

The HTTP Request Rate and HTTP P95 Latency panels should show activity.

The HTTP 5xx Error Rate panel may show zero when no server errors occur.

## 6. Dashboard as Code

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

## 7. Stop the Monitoring Environment

Stop the monitoring containers:

```powershell
docker compose -f .\observability\compose.yml down
```

This stops and removes the monitoring containers and their Compose network.

**Do not use `down -v` during routine operations.**

Removing volumes can destroy stored monitoring data.

The PlatformForge API and PostgreSQL are managed separately from this monitoring Compose project.

## Troubleshooting

### Prometheus Target Is DOWN

Verify that the PlatformForge API is running:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Check the Prometheus target status and confirm that its scrape configuration uses the correct address.

### Grafana Shows No Data

Verify that:

- The API is running.
- Prometheus can scrape `/metrics`.
- The Prometheus datasource is available.
- The dashboard uses datasource UID `prometheus`.
- The selected Grafana time range includes recent traffic.

### Port Conflicts

The local monitoring environment uses:

| Service | Port |
|---|---|
| PlatformForge API | 8000 |
| Prometheus | 9090 |
| Grafana | 3000 |

The Kubernetes observability environment uses separate local port-forward ports:

| Service | Port |
|---|---|
| Kubernetes Prometheus | 9091 |
| Kubernetes Grafana | 3001 |

This allows both environments to be accessed without port conflicts.

## Current Status

The following functionality has been implemented and verified:

- Prometheus HTTP metrics in FastAPI
- Docker Compose monitoring environment
- Prometheus scraping the PlatformForge API
- Grafana datasource provisioning
- PlatformForge API dashboard provisioning
- Four working dashboard panels
- Shared dashboard JSON between Docker Compose and Kubernetes

Future improvements include distributed tracing, centralized logging and alerting.