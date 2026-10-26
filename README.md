# PlatformForge

PlatformForge is an Internal Developer Platform (IDP) learning project built with Python and modern platform engineering technologies.

The project explores how application services can be developed, tested, packaged, deployed, and operated through standardized APIs, automated delivery pipelines, and declarative infrastructure.

Its long-term goal is to provide a developer-facing platform for registering applications, managing deployments, and interacting with infrastructure through automated workflows.

PlatformForge is also designed as a practical demonstration of platform engineering concepts, including Kubernetes, GitOps, CI/CD, database lifecycle management, and infrastructure automation.

**Project status:** Active development. The Platform API, CI/CD pipeline, local Kubernetes deployment, Helm packaging, Argo CD integration, and automated kind bootstrap have been implemented and tested.

## Technology Stack

### Application Development

- **Language:** Python 3.13
- **Web framework:** FastAPI
- **API:** REST with OpenAPI documentation
- **Architecture:** Domain, service, and repository layers; dependency injection; Unit of Work
- **Database:** PostgreSQL 17
- **ORM:** SQLAlchemy
- **Database migrations:** Alembic
- **Testing:** pytest, including PostgreSQL integration tests

### Containers and CI/CD

- **Containerization:** Docker
- **Local development:** Docker Compose
- **CI/CD:** GitLab CI/CD
- **Container registry:** GitLab Container Registry
- **Image versioning:** Git commit SHA
- **Test reporting:** JUnit-compatible reports

### Kubernetes and Platform Engineering

- **Kubernetes:** Local three-node cluster using kind
- **Cluster management:** kubectl
- **Application packaging:** Helm
- **GitOps:** Argo CD
- **GitOps architecture:** App-of-Apps
- **Configuration management:** Kubernetes manifests and Kustomize
- **Database deployment:** PostgreSQL StatefulSet with persistent storage
- **Database migrations:** Alembic executed through a Kubernetes PreSync Job
- **Bootstrap automation:** PowerShell 7

### Planned Technologies

- **Infrastructure as Code:** Terraform
- **Cloud infrastructure:** AWS and Amazon EKS
- **Configuration automation:** Ansible
- **Internal service communication:** gRPC and Protocol Buffers
- **Event streaming:** Apache Kafka and Strimzi
- **Reliable event publishing:** Transactional outbox pattern
- **Observability:** Metrics, logging, distributed tracing, and alerting
- **Security:** Container scanning, stronger secrets management, and additional CI/CD controls

## Architecture Overview

PlatformForge currently consists of a FastAPI service backed by PostgreSQL.

The application uses a layered architecture to separate HTTP concerns, business logic, domain models, and persistence.

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

The infrastructure layer provides automated deployment and lifecycle management.

```text
                    Developer
                        |
                        v
                  GitLab Repository
                        |
                        v
                    GitLab CI
                        |
              +---------+---------+
              |                   |
              v                   v
        Automated Tests      Container Build
                                  |
                                  v
                         GitLab Container Registry


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
              StatefulSet       Helm Chart
                  |                 |
                  v                 +-- Alembic PreSync Job
             Persistent PVC        |
                                    +-- FastAPI Deployment
                                    |
                                    +-- Kubernetes Service
```

The CI/CD pipeline builds and publishes container images. Argo CD manages Kubernetes resources using declarative configuration stored in Git.

A fully integrated image-promotion workflow between CI/CD and GitOps remains a planned improvement.

## Project Structure

The repository is organized around application services and infrastructure automation.

```text
platformforge/
├── .env.example
├── .gitlab-ci.yml
├── README.md
├── compose.yml
│
├── infrastructure/
│   ├── README.md
│   │
│   ├── kind/
│   │   └── cluster.yaml
│   │
│   ├── kubernetes/
│   │   ├── base/
│   │   └── postgres/
│   │
│   ├── helm/
│   │   └── platform-api/
│   │       ├── Chart.yaml
│   │       ├── values.yaml
│   │       ├── values-kind.yaml
│   │       └── templates/
│   │           ├── deployment.yaml
│   │           ├── migration-job.yaml
│   │           └── service.yaml
│   │
│   ├── gitops/
│   │   ├── root.yaml
│   │   └── applications/
│   │       ├── kustomization.yaml
│   │       ├── platform-api.yaml
│   │       └── postgres.yaml
│   │
│   └── scripts/
│       └── bootstrap-kind.ps1
│
└── services/
    └── platform-api/
        ├── app/
        │   ├── api/
        │   ├── db/
        │   ├── domain/
        │   ├── repositories/
        │   ├── schemas/
        │   └── services/
        │
        ├── alembic/
        │   └── versions/
        │
        ├── tests/
        ├── Dockerfile
        ├── alembic.ini
        └── pyproject.toml
```

The repository also contains standalone Kubernetes manifests used during development and earlier deployment stages.

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
- OpenAPI documentation through Swagger UI

### API Documentation

When the API is running locally:

- Swagger UI: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

The API is also accessible inside Kubernetes through its Kubernetes Service.

For local access to the Kubernetes deployment, use `kubectl port-forward` with an explicit cluster context.

## Local Development

### Prerequisites

- Python 3.13
- Docker Desktop with Linux containers
- Git
- PowerShell 7 (recommended for Windows development)

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
Invoke-RestMethod -Uri "http://localhost:8000/health"
```

Stop the environment:

```powershell
docker compose down
```

The PostgreSQL database uses persistent Docker storage.

### Database Migrations

Alembic manages database schema changes.

From `services/platform-api`, with the Python environment and database connection configured:

```powershell
python -m alembic upgrade head
```

In Kubernetes, migrations are executed through an Argo CD PreSync Job as part of the Platform API deployment process.

### Running Tests

The project currently contains **142 collected automated tests**, including PostgreSQL integration tests.

From `services/platform-api`, with development dependencies installed and the required test database available:

```powershell
python -m pytest -q
```

To inspect the test collection without executing tests:

```powershell
python -m pytest --collect-only -q
```

The GitLab CI pipeline prepares PostgreSQL and applies Alembic migrations before executing the automated test suite.

## GitLab CI/CD

GitLab is the primary source repository and CI/CD platform.

The pipeline contains two stages:

1. **test** — Install dependencies, prepare PostgreSQL, apply Alembic migrations, and run pytest.
2. **build** — Build the Platform API Docker image and publish it to GitLab Container Registry.

### Pipeline Behavior

| Pipeline Type | Automated Tests | Docker Image Publication |
|---|---|---|
| Default branch (`main`) | Yes | Yes |
| Feature branch without an open merge request | Yes | No |
| Merge request | Yes | No |

GitLab `workflow: rules` prevent duplicate branch and merge request pipelines when a merge request is open.

### Container Images

The Platform API image is published to GitLab Container Registry using the full Git commit SHA as its tag.

Image naming convention:

```text
<gitlab-registry-project-path>/platform-api:<commit-sha>
```

This provides traceability between source code and published container images.

Published images have also been verified through a local Docker pull and API health-check smoke test.

## Kubernetes Environment

PlatformForge uses kind to provide a reproducible local Kubernetes environment.

The cluster configuration is stored in:

```text
infrastructure/kind/cluster.yaml
```

### Cluster Architecture

The local cluster contains:

- One Kubernetes control-plane node
- Two Kubernetes worker nodes

All nodes run as Docker containers.

PlatformForge uses Kubernetes resources including:

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

The repository includes a PowerShell bootstrap script:

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

The installation completed with:

- PostgreSQL running and ready
- PostgreSQL persistent storage bound
- Alembic migration Job succeeded
- Platform API running and ready
- Root, PostgreSQL, and Platform API Argo CD Applications synchronized and healthy
- API health endpoint responding successfully

For installation instructions, configuration requirements, and operational safeguards, see `infrastructure/README.md`.

**Safety:** Do not delete or recreate existing clusters or persistent database volumes without explicitly verifying their ownership and data-retention requirements.

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

### GitOps Revision Management

The GitOps configuration supports selecting a Git revision for an isolated bootstrap environment.

The current integration work is performed on the `bootstrap-test` branch.

Kustomize propagates the configured revision to the child Applications.

The verified bootstrap workflow uses an explicitly selected Git revision and avoids pruning existing resources during script-controlled synchronization.

**Important:** The `bootstrap-test` branch is an integration and verification branch. It is not the permanent production or default deployment branch.

Changes must be reviewed before merging into `main`, particularly when existing Argo CD installations automatically synchronize from `main`.

## Database Lifecycle and Persistent Storage

PostgreSQL runs as a Kubernetes StatefulSet with persistent storage.

The local kind configuration uses:

- PVC name: `postgres-data`
- Namespace: `platformforge`
- Storage class: `standard`
- Requested capacity: `2Gi`
- Access mode: `ReadWriteOnce`

The project has verified both:

- GitOps adoption of PostgreSQL resources in an existing test environment while retaining the existing PVC.
- Automated PostgreSQL deployment in a newly created kind cluster.

Persistent storage must not be deleted or recreated as part of routine GitOps synchronization.

Successful integration testing does not replace database backup, restore, or disaster-recovery procedures.

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
- The API health endpoint returned:

```text
status: healthy
service: platformforge-api
```

These tests establish a working baseline for further platform development.

## Roadmap

### Completed

- [x] FastAPI Platform API with REST endpoints
- [x] Layered application architecture
- [x] PostgreSQL persistence with SQLAlchemy
- [x] Unit of Work and repository abstractions
- [x] Alembic database migrations
- [x] Automated unit and integration tests
- [x] Docker containerization
- [x] Docker Compose development environment
- [x] GitLab CI/CD with automated testing
- [x] Docker image builds and GitLab Container Registry publication
- [x] Feature branch and merge request pipeline workflows
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

### Next Priorities

- [ ] Update project and infrastructure documentation
- [ ] Review and safely integrate the GitOps changes into `main`
- [ ] Improve CI/CD-to-GitOps image promotion
- [ ] Strengthen Kubernetes reliability and recovery procedures
- [ ] Implement metrics, logging, tracing, and alerting
- [ ] Introduce internal gRPC communication using Protocol Buffers
- [ ] Introduce Kafka-based asynchronous communication using Strimzi
- [ ] Implement the transactional outbox pattern
- [ ] Add Terraform-based AWS infrastructure provisioning
- [ ] Deploy PlatformForge to Amazon EKS
- [ ] Extend security controls and operational automation

## Repository Strategy

**GitLab** is the primary source repository and CI/CD platform.

**GitHub** is maintained as a portfolio mirror.

Development follows a feature branch and merge request workflow, with automated validation before changes are merged into the default branch.

Infrastructure changes require additional care because GitOps controllers may automatically apply changes from tracked branches to existing Kubernetes clusters.

The current GitOps integration is being validated on the isolated `bootstrap-test` branch before a controlled merge into `main`.

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

The next development phase focuses on safely integrating the GitOps changes, improving the CI/CD-to-GitOps delivery workflow, and strengthening platform reliability and observability.

The longer-term roadmap includes gRPC, Kafka, Terraform, AWS, and Amazon EKS.