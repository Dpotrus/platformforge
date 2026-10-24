# PlatformForge Infrastructure

This directory contains the Kubernetes, Helm, kind, and GitOps configuration for PlatformForge.

## Architecture

PlatformForge currently runs in a local kind Kubernetes cluster with:

- One control-plane node and two worker nodes
- PostgreSQL 17 running as a StatefulSet
- A persistent volume claim for PostgreSQL data
- A FastAPI application deployed through Helm and Argo CD
- An Alembic migration Job
- Argo CD configured with the App of Apps pattern

## Directory Structure

| Directory | Purpose |
|---|---|
| `kind/` | Local Kubernetes cluster configuration |
| `kubernetes/base/` | Kubernetes resource manifests |
| `helm/platform-api/` | Helm chart for the FastAPI application |
| `gitops/root.yaml` | Root Argo CD Application bootstrap manifest |
| `gitops/applications/` | Child Argo CD Application definitions |

## GitOps Architecture

The GitOps hierarchy is:

```text
GitLab repository
    |
    v
platformforge-root
    |
    v
platform-api
    |
    v
Helm chart
    |
    +-- FastAPI Deployment
    |
    +-- FastAPI Service
```

Both Argo CD Applications use:

- Automated Sync: enabled
- Self Heal: enabled
- Prune: disabled

The Root Application manages Child Application definitions.

The `platform-api` Child Application renders the Helm chart using `values-kind.yaml`.

The Root Application itself is bootstrapped separately using `kubectl apply`.

## Current Bootstrap Dependencies

A fresh cluster requires the following components to be provisioned in dependency order:

1. Create the kind cluster.
2. Create the `platformforge` namespace.
3. Provision required Kubernetes Secrets.
4. Provision PostgreSQL configuration, storage, Service, and StatefulSet.
5. Wait for PostgreSQL readiness.
6. Run and verify Alembic database migrations.
7. Install Argo CD in the `argocd` namespace.
8. Bootstrap the Root Application.
9. Verify Root and Child Application synchronization.
10. Verify FastAPI readiness and API health.

This describes the intended dependency order, not yet a fully automated installation procedure.

## Required Kubernetes Secrets

The following Secrets are required:

| Secret | Namespace | Purpose |
|---|---|---|
| `postgres-credentials` | `platformforge` | PostgreSQL password |
| `platform-api-db` | `platformforge` | Application database connection URL |
| `gitlab-registry` | `platformforge` | GitLab Container Registry authentication |

Never commit actual Secret values, passwords, tokens, or Kubernetes Secret exports containing credentials to Git.

## Persistent Data Safety

PostgreSQL uses an existing PVC:

- Name: `postgres-data`
- Namespace: `platformforge`
- Storage class: `standard`
- Requested capacity: `2Gi`
- Access mode: `ReadWriteOnce`

Do not delete, replace, or recreate this PVC as part of normal GitOps synchronization.

Before migrating PostgreSQL resources to Argo CD, verify resource ownership, retention behavior, and backup and restore procedures.

## Helm Ownership

The `platform-api` Helm release was originally installed using Helm CLI.

Argo CD now manages the rendered FastAPI Deployment and Service.

Do not run `helm uninstall`, `helm upgrade`, or `helm rollback` against this existing release without first resolving the ownership overlap.

## Database Migrations

Database migrations currently run through a separate Kubernetes Job:

`platform-api-migration`

The Job executes:

```text
alembic upgrade head
```

Database migrations are not yet managed by the GitOps application hierarchy.

A future implementation must define when migration Jobs are created, how their results are verified, and how failures are handled.

## Future Improvements

- Reproducible Argo CD installation with a pinned version
- PowerShell bootstrap automation
- Secure and repeatable Secret provisioning
- PostgreSQL GitOps ownership and persistent data safeguards
- Controlled database migration execution
- Fresh-cluster bootstrap verification
- AWS Kubernetes deployment
