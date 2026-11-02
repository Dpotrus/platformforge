# PlatformForge

**PlatformForge** is an Internal Developer Platform (IDP) learning project built with Python and modern platform engineering technologies.

The project explores how application services can be developed, tested, packaged, deployed, and operated through standardized APIs, automated delivery pipelines, declarative infrastructure, and observability.

Its long-term goal is to provide a developer-facing platform for registering applications, managing deployments, and interacting with infrastructure through automated workflows.

PlatformForge is also a hands-on learning environment for developing practical Platform Engineering skills, including Kubernetes, GitOps, CI/CD, infrastructure automation, observability, and cloud infrastructure.

**Project status:** Active development.

The project currently provides a working FastAPI application, PostgreSQL persistence, automated testing, GitLab CI/CD, Docker containerization, Kubernetes deployments, Helm packaging, Argo CD GitOps integration, and automated kind bootstrap.

A local observability stack has also been implemented and verified, providing metrics, centralized logging, distributed tracing, and log-to-trace correlation.

---

## Technology Stack

### Application Development

- **Language:** Python 3.13
- **Web framework:** FastAPI
- **API:** REST with OpenAPI documentation
- **Architecture:** Domain, service, and repository layers
- **Dependency injection:** FastAPI dependencies
- **Transaction management:** Unit of Work
- **Database:** PostgreSQL 17
- **ORM:** SQLAlchemy 2
- **Database migrations:** Alembic
- **Testing:** pytest, including PostgreSQL integration tests

### Containers and CI/CD

- **Containerization:** Docker
- **Local development:** Docker Compose
- **CI/CD:** GitLab CI/CD
- **Container registry:** GitLab Container Registry
- **Image versioning:** Git commit SHA
- **Test reporting:** JUnit-compatible reports
- **Source control:** Git

### Kubernetes and GitOps

- **Kubernetes:** kind
- **Cluster management:** kubectl
- **Application packaging:** Helm
- **GitOps:** Argo CD
- **GitOps architecture:** App-of-Apps
- **Configuration management:** Kubernetes manifests and Kustomize
- **Database deployment:** PostgreSQL StatefulSet with persistent storage
- **Database migrations:** Alembic through Kubernetes Jobs and Argo CD PreSync hooks
- **Bootstrap automation:** PowerShell 7

### Observability

- **Metrics:** Prometheus
- **Dashboards:** Grafana
- **Distributed tracing:** OpenTelemetry
- **Trace collection:** OpenTelemetry Collector
- **Trace storage:** Grafana Tempo
- **Structured logging:** JSON
- **Log collection:** Grafana Alloy
- **Log aggregation:** Grafana Loki
- **Log-to-trace correlation:** Grafana derived fields
- **Kubernetes monitoring:** Prometheus Operator and ServiceMonitor

### Planned Technologies

- **Alerting:** Prometheus alerting rules and Alertmanager
- **Infrastructure as Code:** Terraform
- **Cloud infrastructure:** AWS and Amazon EKS
- **Configuration automation:** Ansible
- **Internal service communication:** gRPC and Protocol Buffers
- **Event streaming:** Apache Kafka and Strimzi
- **Reliable event publishing:** Transactional outbox pattern
- **Security:** Container scanning, stronger secrets management, and additional CI/CD controls

---

## Architecture Overview

PlatformForge currently consists of a FastAPI service backed by PostgreSQL.

The application uses a layered architecture to separate API concerns, business logic, domain models, and persistence.

```text
                  Platform API
                       |
                       v
                  REST Endpoints
                       |
                       v
                Application Service
                       |
                       v
                  Domain Models
                       |
                       v
             Repository / Unit of Work
                       |
                       v
                    SQLAlchemy
                       |
                       v
                    PostgreSQL
```

This separation allows additional communication interfaces, such as gRPC, to be introduced without duplicating application business logic.

### Delivery Architecture

```text
                   Developer
                       |
                       v
                 GitLab Repository
                       |
                       v
                    GitLab CI
                       |
              +--------+--------+
              |                 |
              v                 v
        Automated Tests    Container Build
                                |
                                v
                       GitLab Container Registry
```

The CI/CD pipeline validates the application, builds container images, and publishes versioned artifacts.

Kubernetes deployment configuration is maintained separately through GitOps.

```text
                  GitOps Configuration
                          |
                          v
                        Argo CD
                          |
                          v
                   Root Application
                          |
                 +--------+--------+
                 |                 |
                 v                 v
             PostgreSQL        Platform API
                 |                 |
                 v                 v
             Kustomize         Helm Chart
                 |                 |
                 v                 +-- Alembic PreSync Job
             StatefulSet          |
                 |                 +-- FastAPI Deployment
                 v                 |
             Persistent PVC       +-- Kubernetes Service
```

The Argo CD App-of-Apps integration and automated bootstrap have been successfully verified.

A fully integrated CI/CD-to-GitOps image-promotion workflow remains a planned improvement.

---

## Project Structure

```text
platformforge/
├── .env.example
├── .gitlab-ci.yml
├── README.md
├── compose.yml
│
├── infrastructure/
│   ├── README.md
│   ├── kind/
│   ├── kubernetes/
│   ├── helm/
│   ├── gitops/
│   ├── observability/
│   │   ├── README.md
│   │   └── kube-prometheus-stack/
│   └── scripts/
│
├── observability/
│   ├── README.md
│   ├── compose.yml
│   ├── alloy/
│   ├── collector/
│   ├── grafana/
│   ├── prometheus/
│   └── tempo/
│
└── services/
    └── platform-api/
        ├── app/
        │   ├── api/
        │   ├── db/
        │   ├── domain/
        │   ├── observability/
        │   ├── repositories/
        │   ├── schemas/
        │   └── services/
        │
        ├── alembic/
        ├── tests/
        ├── Dockerfile
        ├── alembic.ini
        └── pyproject.toml
```

The repository contains separate configurations for application development, Kubernetes infrastructure, and observability.

Some standalone Kubernetes manifests are retained for development and reference.

---

## Platform API

The Platform API is implemented using FastAPI.

### Implemented Capabilities

- Application registration through REST endpoints
- Application retrieval
- Domain model validation
- Layered application architecture
- Dependency injection
- Repository abstraction
- Unit of Work
- PostgreSQL persistence
- SQLAlchemy ORM models
- Alembic database migrations
- Automated unit and integration tests
- Health-check endpoint
- Prometheus metrics endpoint
- Structured JSON logging
- Distributed tracing instrumentation
- OpenAPI documentation through Swagger UI

### API Endpoints

The application exposes endpoints including:

| Endpoint | Purpose |
|---|---|
| `/health` | Application health check |
| `/metrics` | Prometheus metrics |
| `/api/v1/applications/` | Application registration and retrieval |
| `/docs` | Swagger UI |

### API Documentation

When the API is running locally:

- Swagger UI: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`
- Metrics: `http://localhost:8000/metrics`

The API can also be accessed inside Kubernetes through its Kubernetes Service.

Use `kubectl port-forward` with an explicit cluster context when accessing a Kubernetes deployment locally.

---

## Local Development

### Prerequisites

- Python 3.13
- Docker Desktop with Linux containers
- Git
- PowerShell 7 (recommended for Windows development)

Additional tools such as kind, kubectl, and Helm are required for Kubernetes development.

### Environment Configuration

The repository contains `.env.example`, which documents environment variables required for local development.

Create a local `.env` file and configure the development database credentials.

Do not commit `.env` files, passwords, access tokens, or production secrets to version control.

### Start the Application

From the repository root:

```powershell
docker compose up --build -d
```

Check the running containers:

```powershell
docker compose ps
```

Verify the API health endpoint:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Stop the environment:

```powershell
docker compose down
```

The PostgreSQL database uses persistent Docker storage.

Avoid deleting Docker volumes unless an intentional database reset is required.

### Database Migrations

Alembic manages database schema changes.

From `services/platform-api`, with the Python environment and database connection configured:

```powershell
python -m alembic upgrade head
```

In GitOps-managed Kubernetes deployments, migrations are executed through an Argo CD PreSync Job.

### Running Tests

The latest verified local test run completed successfully with:

```text
206 passed
```

Run the tests from the Platform API directory:

```powershell
cd .\services\platform-api

python -m pytest -q
```

To inspect test collection without executing tests:

```powershell
python -m pytest --collect-only -q
```

The test environment requires the appropriate database configuration.

The GitLab CI pipeline prepares PostgreSQL and applies Alembic migrations before running the automated test suite.

---

## GitLab CI/CD

GitLab is the primary source repository and CI/CD platform.

The pipeline contains two main stages:

1. **test** — Install dependencies, prepare PostgreSQL, apply Alembic migrations, and run pytest.
2. **build** — Build the Platform API Docker image and publish it to GitLab Container Registry.

### Pipeline Behavior

| Pipeline Type | Automated Tests | Docker Image Publication |
|---|---|---|
| Default branch (`main`) | Yes | Yes |
| Feature branch without an open merge request | Yes | No |
| Merge request | Yes | No |

GitLab workflow rules prevent duplicate branch and merge request pipelines when a merge request is open.

### Container Images

The Platform API image is published to GitLab Container Registry using the full Git commit SHA as its tag.

Image naming convention:

```text
<gitlab-registry-project-path>/platform-api:<commit-sha>
```

This provides traceability between source code and published container images.

Published images have also been verified through a local Docker pull and API health-check smoke test.

### Current Delivery Status

The CI/CD pipeline has been implemented and successfully verified.

The latest observability changes were merged into `main`, and the corresponding GitLab pipeline completed successfully.

**Planned improvement:** Automate image promotion from GitLab CI/CD into GitOps-managed deployment configuration.

---

## Kubernetes Environment

PlatformForge uses kind to provide reproducible local Kubernetes environments.

### Main GitOps Environment

The primary Kubernetes configuration is stored in:

```text
infrastructure/kind/cluster.yaml
```

The verified GitOps bootstrap environment uses:

- One Kubernetes control-plane node
- Two Kubernetes worker nodes

The environment includes:

- Namespaces
- Deployments
- Services
- ConfigMaps
- Secrets
- StatefulSets
- PersistentVolumeClaims
- Jobs

The Platform API is packaged using Helm.

PostgreSQL is deployed using Kubernetes manifests and Kustomize.

### Automated Bootstrap

The repository includes:

```text
infrastructure/scripts/bootstrap-kind.ps1
```

The script supports:

- Environment preflight checks
- kind cluster creation
- Argo CD installation
- Kubernetes namespace and Secret preparation
- GitOps revision verification
- Root Application installation
- Ordered PostgreSQL and Platform API synchronization
- Readiness and synchronization verification

The automated bootstrap workflow has been successfully tested against a newly created three-node kind cluster.

The verified installation included:

- PostgreSQL running and ready
- PostgreSQL persistent storage bound
- Alembic migration Job completed successfully
- Platform API running and ready
- Root and child Argo CD Applications synchronized and healthy
- API health endpoint responding successfully

For detailed installation instructions and operational safeguards, see:

**[Infrastructure Documentation](infrastructure/README.md)**

**Safety:** Do not delete or recreate existing clusters or persistent database volumes without verifying ownership and data-retention requirements.

---

## GitOps with Argo CD

PlatformForge uses Argo CD and the App-of-Apps pattern.

The Root Application manages two child Applications:

- `platformforge-postgres`
- `platform-api`

The PostgreSQL Application manages database infrastructure.

The Platform API Application renders the Helm chart, including the Alembic migration Job.

### Deployment Ordering

The bootstrap workflow coordinates deployment in the following order:

1. Prepare Kubernetes namespaces and Secrets.
2. Install Argo CD.
3. Bootstrap the Root Application.
4. Synchronize PostgreSQL.
5. Wait for PostgreSQL readiness.
6. Synchronize the Platform API.
7. Execute Alembic migrations through the PreSync hook.
8. Verify the Platform API deployment.

The child Applications use controlled synchronization rather than independent automated synchronization.

This ensures that PostgreSQL readiness is verified before the API deployment proceeds.

### GitOps Integration Status

The GitOps integration was initially developed and verified using the `bootstrap-test` branch.

The changes were subsequently integrated through `merge-preparation` and merged into `main`.

The original integration tests and verification results are retained in the infrastructure documentation.

The GitOps configuration currently targets `main`.

**Important:** Before applying infrastructure changes, verify the Git revision and synchronization policies used by the target Kubernetes environment.

The existence of GitOps configuration in `main` does not imply that every local cluster is currently running or synchronized with the latest revision.

---

## Database Lifecycle and Persistent Storage

PostgreSQL runs as a Kubernetes StatefulSet with persistent storage.

The verified local GitOps configuration uses:

| Property | Value |
|---|---|
| PVC name | `postgres-data` |
| Namespace | `platformforge` |
| Storage class | `standard` |
| Requested capacity | `2Gi` |
| Access mode | `ReadWriteOnce` |

The project has verified:

- GitOps adoption of PostgreSQL resources in an existing test environment while preserving the existing PVC.
- Automated PostgreSQL deployment in a newly created kind cluster.

Persistent storage must not be deleted or recreated as part of routine GitOps synchronization.

Successful integration testing does not replace database backup, restore, or disaster-recovery procedures.

These remain important future improvements.

---

## Observability

PlatformForge includes observability instrumentation and supporting infrastructure for monitoring and troubleshooting the application.

The local Docker Compose environment provides three primary observability signals:

1. **Metrics**
2. **Logs**
3. **Distributed traces**

### Metrics

Prometheus collects HTTP metrics exposed by the Platform API.

Grafana provides dashboards for:

- HTTP request rate
- HTTP 5xx error rate
- HTTP P95 latency
- HTTP requests in progress

The dashboard configuration is maintained as code and shared between the local Docker Compose and Kubernetes observability environments.

### Distributed Tracing

OpenTelemetry instruments FastAPI and SQLAlchemy.

The tracing pipeline is:

```text
PlatformForge API
       |
       v
OpenTelemetry Collector
       |
       v
   Grafana Tempo
       |
       v
  Grafana Explore
```

Distributed tracing has been verified end-to-end.

HTTP server spans and SQLAlchemy database spans can be inspected within the same trace.

### Centralized Logging

The Platform API produces structured JSON logs.

The local logging pipeline is:

```text
PlatformForge API
       |
       v
   Docker Logs
       |
       v
   Grafana Alloy
       |
       v
    Grafana Loki
       |
       v
  Grafana Explore
```

Alloy collects application container logs and forwards them to Loki.

The logging implementation includes request logging and trace correlation fields.

### Logs-to-Traces Correlation

Application logs include OpenTelemetry trace identifiers when tracing context is available.

Grafana uses a Loki derived field to link log entries to corresponding traces in Tempo.

This allows developers to move from an application log entry to the distributed trace associated with the same request.

The integration has been verified in the local Docker Compose environment.

### Observability Environments

PlatformForge maintains two separate observability environments.

| Environment | Purpose | Verified Capabilities |
|---|---|---|
| Docker Compose | Local application development | Metrics, logs, traces, Logs-to-Traces |
| Kubernetes | Kubernetes monitoring and application metrics | Prometheus Operator, ServiceMonitor, Grafana dashboards |

The Kubernetes observability environment runs in a dedicated kind cluster.

It is isolated from the existing GitOps environments.

The Kubernetes monitoring stack currently uses Helm and Kubernetes commands rather than Argo CD.

The local Docker Compose logging and tracing capabilities should not be assumed to be deployed in Kubernetes.

### Documentation

- **[Local Observability](observability/README.md)** — Docker Compose, Prometheus, OpenTelemetry, Tempo, Loki, Alloy, and Grafana.
- **[Kubernetes Observability](infrastructure/observability/README.md)** — kind, kube-prometheus-stack, ServiceMonitor, and Kubernetes dashboards.

### Planned Improvements

- Prometheus alerting rules
- Alertmanager integration
- Alert notification testing
- Additional Kubernetes observability capabilities
- GitOps management of Kubernetes monitoring
- Persistent monitoring storage
- Improved operational recovery procedures

---

## Verified Infrastructure Milestones

The following infrastructure scenarios have been tested successfully.

### Existing-Cluster GitOps Integration

- Argo CD Root and child Applications synchronized successfully.
- PostgreSQL resources were managed through GitOps.
- The existing PostgreSQL PVC was preserved.
- PostgreSQL remained ready.
- The Platform API deployed successfully.
- The Alembic migration Job completed successfully.
- The API health endpoint responded successfully.

### Fresh-Cluster Automated Bootstrap

- A new three-node kind cluster was created.
- Argo CD was installed.
- Required Kubernetes Secrets were prepared.
- A published GitLab GitOps revision was verified.
- The Root Application created the child Applications.
- PostgreSQL synchronized and became ready.
- The Alembic PreSync Job succeeded.
- The Platform API synchronized and became healthy.
- The API health endpoint responded successfully.

### Local Observability Verification

- Prometheus successfully scraped Platform API metrics.
- Grafana dashboards displayed application metrics.
- OpenTelemetry exported FastAPI and SQLAlchemy spans.
- Tempo stored and exposed distributed traces.
- Alloy collected structured application logs.
- Loki received and exposed application logs.
- Grafana linked log entries to corresponding Tempo traces.

### Automated Testing

The latest verified local Platform API test run completed with:

```text
206 passed
```

The GitLab CI pipeline also completed successfully after the latest centralized logging changes.

---

## Roadmap

### Completed — Application Foundation

- [x] FastAPI Platform API with REST endpoints
- [x] Layered application architecture
- [x] Domain model validation
- [x] PostgreSQL persistence with SQLAlchemy
- [x] Unit of Work and repository abstractions
- [x] Alembic database migrations
- [x] Automated unit and integration tests

### Completed — Containers and CI/CD

- [x] Docker containerization
- [x] Docker Compose development environment
- [x] GitLab CI/CD with automated testing
- [x] Docker image builds and GitLab Container Registry publication
- [x] Git commit SHA image versioning
- [x] Feature branch and merge request pipeline workflows

### Completed — Kubernetes and GitOps

- [x] Local three-node Kubernetes cluster using kind
- [x] Kubernetes Deployments, Services, ConfigMaps, and Secrets
- [x] PostgreSQL StatefulSet and persistent storage
- [x] Helm chart for the Platform API
- [x] Argo CD App-of-Apps integration
- [x] PostgreSQL GitOps integration
- [x] Alembic PreSync migration Job
- [x] PowerShell-based Kubernetes bootstrap automation
- [x] Fresh-cluster bootstrap verification
- [x] Existing-cluster PostgreSQL PVC preservation test
- [x] GitOps integration merged into `main`

### Completed — Observability

- [x] Prometheus metrics instrumentation
- [x] Grafana metrics dashboards
- [x] Kubernetes Prometheus Operator and ServiceMonitor integration
- [x] OpenTelemetry distributed tracing
- [x] FastAPI tracing instrumentation
- [x] SQLAlchemy tracing instrumentation
- [x] Grafana Tempo trace storage and exploration
- [x] Structured JSON application logging
- [x] Centralized logging with Grafana Alloy and Loki
- [x] Grafana Logs-to-Traces correlation

### Next Priorities

- [ ] Update and synchronize project documentation
- [ ] Implement Prometheus alerting rules
- [ ] Integrate and verify Alertmanager notifications
- [ ] Improve CI/CD-to-GitOps image promotion
- [ ] Strengthen Kubernetes reliability and recovery procedures
- [ ] Improve Kubernetes observability and GitOps integration
- [ ] Introduce internal gRPC communication using Protocol Buffers
- [ ] Introduce Kafka-based asynchronous communication using Strimzi
- [ ] Implement the transactional outbox pattern
- [ ] Add Terraform-based AWS infrastructure provisioning
- [ ] Deploy PlatformForge to Amazon EKS
- [ ] Extend security controls and operational automation

---

## Repository Strategy

**GitLab** is the primary source repository and CI/CD platform.

**GitHub** is maintained as a portfolio mirror.

Development follows a feature branch and merge request workflow, with automated validation before changes are merged into the default branch.

Infrastructure changes require additional care because GitOps controllers may automatically apply changes from tracked branches to existing Kubernetes clusters.

The original GitOps integration was developed and verified on `bootstrap-test` before being merged into `main`.

Future infrastructure changes must be reviewed against the configuration and synchronization policies of the target environment.

---

## Project Status

**Under active development.**

PlatformForge currently provides a working application and infrastructure foundation:

- FastAPI REST API backed by PostgreSQL
- Automated testing and GitLab CI/CD
- Container builds and registry publication
- Helm-based Kubernetes application deployment
- PostgreSQL StatefulSet with persistent storage
- Argo CD App-of-Apps integration
- Controlled database migrations
- Automated kind cluster bootstrap
- Prometheus metrics and Grafana dashboards
- OpenTelemetry distributed tracing
- Centralized logging with Loki and Alloy
- Logs-to-Traces correlation

The next development priorities are alerting, improved CI/CD-to-GitOps delivery, and stronger operational reliability.

The longer-term roadmap includes gRPC, Kafka, Terraform, AWS, and Amazon EKS.

The project remains a practical learning environment for building, deploying, observing, and operating modern application platforms.