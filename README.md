# PlatformForge

PlatformForge is an Internal Developer Platform (IDP) learning project built with Python and modern platform engineering tools.

The project demonstrates how to build, deploy, automate, and operate application services using cloud-native technologies.

## Technology Stack

- **Backend:** Python, FastAPI, REST API
- **Database:** PostgreSQL, SQLAlchemy, Alembic
- **Containers:** Docker, Docker Compose
- **Orchestration:** Kubernetes, Helm
- **CI/CD:** GitLab CI/CD
- **GitOps:** Argo CD
- **Infrastructure:** AWS, Terraform, Ansible
- **Service communication:** gRPC, Protocol Buffers
- **Event-driven architecture:** Apache Kafka
- **Observability:** To be implemented

## Project Structure

```text
platformforge/
├── compose.yml
└── services/
    └── platform-api/
        ├── app/
        ├── tests/
        └── pyproject.toml
```

## Current Progress

The Platform API is implemented with FastAPI and includes:

- Application registration through REST endpoints
- Domain, service, and repository layers
- Dependency injection
- Automated tests using pytest
- PostgreSQL development environment using Docker Compose
- SQLAlchemy database configuration
- GitLab repository with automatic GitHub mirroring

## Roadmap

1. PostgreSQL persistence and Alembic migrations
2. Containerize the Platform API
3. Kubernetes deployment and Helm charts
4. GitLab CI/CD pipelines
5. GitOps using Argo CD
6. Infrastructure automation on AWS
7. Internal gRPC services
8. Kafka-based asynchronous events
9. Observability, security, and operational improvements

## Repository Strategy

GitLab is the primary source repository and CI/CD platform.

GitHub is maintained as a public portfolio mirror.

## Status

Under active development.