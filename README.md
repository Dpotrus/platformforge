# PlatformForge

PlatformForge is an Internal Developer Platform (IDP) learning project built with Python and modern platform engineering tools.

The project demonstrates how to build, test, deploy, automate, and operate application services using cloud-native technologies.

The long-term goal is to develop a platform that enables developers to register applications, manage deployments, and interact with infrastructure through standardized APIs and automated workflows.

## Technology Stack

### Implemented

- **Backend:** Python 3.13, FastAPI, REST API
- **Architecture:** Domain, service, and repository layers; dependency injection; unit of work
- **Database:** PostgreSQL 17, SQLAlchemy, Alembic
- **Testing:** pytest, PostgreSQL integration tests, JUnit test reports
- **Containers:** Docker, Docker Compose
- **CI/CD:** GitLab CI/CD, automated tests, Docker image builds
- **Container Registry:** GitLab Container Registry, commit-SHA-based image tagging
- **Version Control:** GitLab as the primary repository, GitHub as a portfolio mirror

### Local Kubernetes Environment

- **Kubernetes:** Local three-node cluster using kind (Kubernetes IN Docker)
- **Cluster Management:** kubectl
- **Packaging Tool:** Helm installed; application charts not yet implemented

### Planned

- **GitOps:** Argo CD
- **Infrastructure as Code:** Terraform
- **Cloud Infrastructure:** AWS, Amazon EKS
- **Configuration Automation:** Ansible
- **Internal Service Communication:** gRPC, Protocol Buffers
- **Event-Driven Architecture:** Apache Kafka, Strimzi
- **Reliability:** Transactional outbox pattern
- **Observability:** Metrics, logs, distributed tracing, alerting
- **Security:** Container scanning, secrets management, and additional CI/CD security controls

## Project Structure

```text
platformforge/
├── .gitlab-ci.yml
├── .env.example
├── README.md
├── compose.yml
├── infrastructure/
│   └── kind/
│       └── cluster.yaml
└── services/
    └── platform-api/
        ├── app/
        │   ├── api/
        │   ├── db/
        │   ├── domain/
        │   ├── repositories/
        │   ├── schemas/
        │   └── services/
        ├── alembic/
        │   └── versions/
        ├── tests/
        ├── Dockerfile
        ├── alembic.ini
        └── pyproject.toml
```

The repository is organized to support additional services, Kubernetes resources, Helm charts, and infrastructure automation as the platform evolves.

## Platform API

The Platform API is implemented using FastAPI.

Current capabilities include:

- Application registration through REST endpoints
- Layered application architecture
- Dependency injection
- Database-backed persistence using PostgreSQL
- SQLAlchemy ORM models
- Alembic database migrations
- Automated unit and integration tests
- Health-check endpoint
- OpenAPI documentation through FastAPI Swagger UI

### API Documentation

When running the API locally, interactive documentation is available at:

- Swagger UI: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

## Local Development

### Prerequisites

- Python 3.13
- Docker Desktop with Linux containers
- Git
- PowerShell 7 (recommended for the Windows development workflow)

### Environment Configuration

The repository contains an `.env.example` file documenting the environment variables required by Docker Compose.

Create a local `.env` file and configure the development database credentials.

Do not commit `.env` files or production secrets to version control.

### Start the Application

From the repository root:

```powershell
docker compose up --build -d
```

Check container status:

```powershell
docker compose ps
```

Check the API health endpoint:

```powershell
Invoke-RestMethod http://localhost:8000/health
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

### Running Tests

The project currently contains 142 automated tests, including PostgreSQL integration tests.

From `services/platform-api`, with development dependencies installed and the test database prepared:

```powershell
python -m pytest -q
```

The GitLab CI pipeline runs database migrations before executing the automated test suite.

## GitLab CI/CD

GitLab is the primary CI/CD platform.

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

Published images have also been verified through a local Docker pull and API health check smoke test.

## Local Kubernetes Environment

PlatformForge uses kind to provide a reproducible local Kubernetes environment.

The cluster configuration is stored in:

```text
infrastructure/kind/cluster.yaml
```

### Cluster Architecture

The local cluster consists of:

- One Kubernetes control-plane node
- Two Kubernetes worker nodes

All nodes run as Docker containers.

### Create the Cluster

From the repository root:

```powershell
kind create cluster --config infrastructure/kind/cluster.yaml
```

### Verify the Cluster

```powershell
kind get clusters
kubectl config current-context
kubectl get nodes -o wide
kubectl get pods -n kube-system
kubectl cluster-info
```

The expected Kubernetes context is:

```text
kind-platformforge
```

All three nodes should report `Ready`.

### Delete the Cluster

```powershell
kind delete cluster --name platformforge
```

**Warning:** Deleting the cluster removes its Kubernetes resources and may destroy data stored inside the cluster.

Kubernetes deployments for PlatformForge services will be introduced in subsequent development steps.

## Roadmap

### Completed

- [x] FastAPI Platform API with REST endpoints
- [x] Layered application architecture
- [x] PostgreSQL persistence with SQLAlchemy
- [x] Alembic database migrations
- [x] Automated unit and integration tests
- [x] Docker containerization
- [x] Docker Compose development environment
- [x] GitLab CI/CD with automated testing
- [x] Docker image builds and GitLab Container Registry publication
- [x] Feature branch and merge request pipeline workflows
- [x] Local three-node Kubernetes cluster using kind

### Upcoming

- [ ] Kubernetes namespaces, Deployments, Services, ConfigMaps, and Secrets
- [ ] Kubernetes health probes and resource management
- [ ] Helm charts for PlatformForge services
- [ ] GitOps deployment using Argo CD
- [ ] Terraform infrastructure provisioning on AWS
- [ ] Amazon EKS deployment
- [ ] Internal gRPC services using Protocol Buffers
- [ ] Kafka-based asynchronous communication using Strimzi
- [ ] Transactional outbox pattern for reliable event publishing
- [ ] Metrics, logging, tracing, and alerting
- [ ] Security and operational improvements

## Repository Strategy

**GitLab** is the primary source repository and CI/CD platform.

**GitHub** is maintained as a public portfolio mirror.

Development follows a feature branch and merge request workflow, with automated validation before changes are merged into the default branch.

## Project Status

**Under active development.**

The Platform API, PostgreSQL persistence, automated testing, Docker containerization, GitLab CI/CD, and local Kubernetes cluster are implemented.

The next development phase focuses on deploying PlatformForge services to Kubernetes, followed by Helm and GitOps.