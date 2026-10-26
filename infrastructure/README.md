# PlatformForge Infrastructure

This directory contains the Kubernetes, Helm, kind, GitOps, and bootstrap automation configuration for PlatformForge.

The infrastructure is designed to demonstrate practical platform engineering concepts, including declarative deployments, persistent storage, database lifecycle management, deployment orchestration, and reproducible Kubernetes environments.

**Current status:** Local Kubernetes deployment, Helm packaging, Argo CD App-of-Apps integration, PostgreSQL GitOps management, Alembic PreSync migrations, and automated kind bootstrap have been implemented and verified.

## Architecture

PlatformForge currently runs in a local three-node kind Kubernetes cluster.

The environment includes:

- One Kubernetes control-plane node
- Two Kubernetes worker nodes
- PostgreSQL 17 deployed as a StatefulSet
- Persistent storage for PostgreSQL
- A FastAPI application deployed through Helm
- An Alembic database migration Job
- Argo CD configured using the App-of-Apps pattern
- PowerShell automation for Kubernetes bootstrap

The infrastructure separates application deployment from database infrastructure while coordinating their installation order.

### Architecture Overview

```text
                       GitLab Repository
                              |
                              v
                         Argo CD
                              |
                              v
                     platformforge-root
                              |
                 +------------+------------+
                 |                         |
                 v                         v
       platformforge-postgres         platform-api
                 |                         |
                 v                         v
             Kustomize                 Helm Chart
                 |                         |
          +------+------+           +------+------+
          |      |      |           |             |
          v      v      v           v             v
       Config  Service  PVC      PreSync Job   Deployment
        Map              |           |             |
                         v           v             v
                    StatefulSet   Alembic        FastAPI
                         |
                         v
                     PostgreSQL
```

The bootstrap script coordinates the initial deployment so PostgreSQL becomes ready before the Platform API is synchronized.

## Directory Structure

```text
infrastructure/
├── README.md
│
├── kind/
│   └── cluster.yaml
│
├── kubernetes/
│   ├── base/
│   │   ├── namespace.yaml
│   │   ├── platform-api-deployment.yaml
│   │   ├── platform-api-migration-job.yaml
│   │   ├── platform-api-service.yaml
│   │   ├── postgres-configmap.yaml
│   │   ├── postgres-pvc.yaml
│   │   ├── postgres-service.yaml
│   │   └── postgres-statefulset.yaml
│   │
│   └── postgres/
│       ├── kustomization.yaml
│       ├── postgres-configmap.yaml
│       ├── postgres-pvc.yaml
│       ├── postgres-service.yaml
│       └── postgres-statefulset.yaml
│
├── helm/
│   └── platform-api/
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── values-kind.yaml
│       └── templates/
│           ├── deployment.yaml
│           ├── migration-job.yaml
│           └── service.yaml
│
├── gitops/
│   ├── root.yaml
│   └── applications/
│       ├── kustomization.yaml
│       ├── platform-api.yaml
│       └── postgres.yaml
│
└── scripts/
    └── bootstrap-kind.ps1
```

### Directory Responsibilities

| Directory | Purpose |
|---|---|
| `kind/` | Local Kubernetes cluster configuration |
| `kubernetes/base/` | Standalone Kubernetes manifests used during development |
| `kubernetes/postgres/` | PostgreSQL resources managed through Kustomize and Argo CD |
| `helm/platform-api/` | Helm chart for the FastAPI application |
| `gitops/root.yaml` | Root Argo CD Application bootstrap manifest |
| `gitops/applications/` | Child Argo CD Applications and revision configuration |
| `scripts/` | Infrastructure bootstrap automation |

The standalone manifests under `kubernetes/base/` are retained for development and reference.

The current GitOps deployment uses the PostgreSQL Kustomize configuration and the Platform API Helm chart.

## GitOps Architecture

PlatformForge uses Argo CD and the App-of-Apps pattern.

The Root Application manages two child Applications:

1. `platformforge-postgres`
2. `platform-api`

### Root Application

The Root Application is defined in:

```text
infrastructure/gitops/root.yaml
```

It points to:

```text
infrastructure/gitops/applications/
```

The Root Application creates and manages the child Application definitions.

For a fresh-cluster bootstrap, the Root Application uses automated synchronization with self-healing enabled and pruning disabled.

### PostgreSQL Application

The PostgreSQL Application is defined in:

```text
infrastructure/gitops/applications/postgres.yaml
```

It references:

```text
infrastructure/kubernetes/postgres/
```

This directory contains the Kustomize configuration for PostgreSQL.

The managed resources include:

- ConfigMap
- Service
- StatefulSet
- PersistentVolumeClaim

The PostgreSQL child Application does not enable independent automated synchronization.

Its synchronization is explicitly controlled by the bootstrap script.

### Platform API Application

The Platform API Application is defined in:

```text
infrastructure/gitops/applications/platform-api.yaml
```

It references the Helm chart:

```text
infrastructure/helm/platform-api/
```

The chart is rendered using:

```text
values-kind.yaml
```

The chart includes:

- FastAPI Deployment
- FastAPI Service
- Alembic migration Job

The migration Job runs as an Argo CD PreSync hook.

The Platform API child Application does not enable independent automated synchronization.

### Synchronization Policy

| Application | Automated Sync | Self-Heal | Pruning |
|---|---|---|---|
| Root | Enabled during fresh bootstrap | Enabled | Disabled |
| PostgreSQL | Disabled | Not enabled | Disabled during script-controlled sync |
| Platform API | Disabled | Not enabled | Disabled during script-controlled sync |

This configuration is intentional.

The Root Application establishes the GitOps hierarchy.

The bootstrap script then synchronizes PostgreSQL and Platform API in dependency order.

This prevents the Platform API from being synchronized before PostgreSQL readiness has been verified.

**Important:** The Root Application is automatically synchronized during the fresh-cluster bootstrap workflow. Existing test environments may use a different Root synchronization policy. Do not assume that all clusters have identical settings.

## GitOps Revision Management

The child Application definitions contain:

```yaml
targetRevision: main
```

However, the current integration branch uses Kustomize to override this value.

The configuration is defined in:

```text
infrastructure/gitops/applications/kustomization.yaml
```

The current integration configuration contains:

```yaml
configMapGenerator:
  - name: platformforge-gitops-config
    namespace: argocd
    literals:
      - revision=bootstrap-test

generatorOptions:
  disableNameSuffixHash: true
```

A Kustomize replacement propagates the configured revision into:

```text
spec.source.targetRevision
```

for the child Applications.

This allows the current integration tests to use the isolated `bootstrap-test` branch instead of deploying child Applications from `main`.

The bootstrap script also verifies that the requested GitOps revision is published to GitLab before installation.

### Important Branch Safety

The current GitOps integration work is performed on:

```text
bootstrap-test
```

This is a temporary integration and verification branch.

The original PlatformForge cluster follows `main`.

Changes must not be merged into `main` without reviewing the resulting Argo CD synchronization behavior.

Before merging, the hardcoded integration revision in the Kustomize configuration must be reviewed and replaced with the intended long-term revision strategy.

## Automated Kubernetes Bootstrap

The bootstrap script is located at:

```text
infrastructure/scripts/bootstrap-kind.ps1
```

The script supports:

- Prerequisite checks
- kind cluster creation
- Kubernetes cluster identity verification
- Argo CD installation
- Namespace and Secret preparation
- Published GitOps revision verification
- Root Application installation
- Ordered child Application synchronization
- PostgreSQL readiness verification
- Application synchronization and health verification

The automated workflow has been successfully tested in a newly created three-node kind cluster.

### Prerequisites

The verified local workflow uses:

- Windows with PowerShell 7
- Docker Desktop with Linux containers
- kind
- kubectl
- Git
- Access to the GitLab repository
- Credentials required for PostgreSQL and GitLab Container Registry

Commands below are intended to be executed from the repository root.

### Safety Requirements

Always specify the intended cluster explicitly.

Do not assume the current kubectl context points to the correct cluster.

For verification commands, use:

```powershell
kubectl --context <target-context> ...
```

The bootstrap script accepts an explicit cluster name.

Avoid running destructive commands against existing clusters.

In particular, never delete or recreate a PostgreSQL PVC containing data as part of routine bootstrap or GitOps operations.

### Step 1 – Create a New kind Cluster

The following command shows the verified bootstrap invocation.

Use a new, unique cluster name for a new installation.

```powershell
.\infrastructure\scripts\bootstrap-kind.ps1 `
    -ClusterName <new-cluster-name> `
    -GitOpsRevision bootstrap-test `
    -Create
```

The `-Create` stage creates the Kubernetes cluster using the repository's kind configuration.

The verified environment contains one control-plane node and two worker nodes.

**Do not use an existing cluster name unless you have explicitly confirmed the intended operation.**

### Step 2 – Install Argo CD

```powershell
.\infrastructure\scripts\bootstrap-kind.ps1 `
    -ClusterName <new-cluster-name> `
    -GitOpsRevision bootstrap-test `
    -InstallArgoCD
```

This stage installs Argo CD into the target Kubernetes cluster.

The installation waits for the Argo CD components to become ready.

### Step 3 – Prepare PlatformForge

Before preparing the environment, configure the required credentials in the current PowerShell session.

The bootstrap script reads the following environment variables:

| Environment Variable | Purpose |
|---|---|
| `PLATFORMFORGE_POSTGRES_PASSWORD` | PostgreSQL password |
| `PLATFORMFORGE_REGISTRY_USERNAME` | GitLab Container Registry username |
| `PLATFORMFORGE_REGISTRY_TOKEN` | GitLab Container Registry access token |

Do not commit credential values to Git or include them in terminal logs shared publicly.

The variables can be set privately in the PowerShell session.

Run:

```powershell
.\infrastructure\scripts\bootstrap-kind.ps1 `
    -ClusterName <new-cluster-name> `
    -GitOpsRevision bootstrap-test `
    -PreparePlatformForge
```

This stage prepares the PlatformForge namespace and required Kubernetes Secrets.

### Step 4 – Install GitOps Applications

The GitOps installation stage requires `-PreparePlatformForge` in the same invocation.

This requirement applies even if the preparation stage was completed previously.

Run:

```powershell
.\infrastructure\scripts\bootstrap-kind.ps1 `
    -ClusterName <new-cluster-name> `
    -GitOpsRevision bootstrap-test `
    -PreparePlatformForge `
    -InstallGitOpsRoot
```

The script verifies the published GitOps revision and then coordinates installation.

The expected deployment sequence is:

1. Install the Root Application.
2. Create the child Application definitions.
3. Synchronize PostgreSQL.
4. Wait for PostgreSQL readiness.
5. Synchronize the Platform API.
6. Execute Alembic migrations through the PreSync hook.
7. Verify application synchronization and health.

The successful integration test produced:

```text
Application synchronized and healthy: platformforge-postgres
PostgreSQL ready.
Application synchronized and healthy: platform-api
Requested bootstrap stages completed.
```

### Bootstrap Revision Warning

The commands above document the verified `bootstrap-test` workflow.

They are not intended as permanent production installation commands.

The selected GitOps revision must be reviewed before using the script with other branches or environments.

## Required Kubernetes Secrets

The following Secrets are required in the `platformforge` namespace.

| Secret | Type | Purpose |
|---|---|---|
| `postgres-credentials` | Opaque | PostgreSQL authentication |
| `platform-api-db` | Opaque | Application database connection |
| `gitlab-registry` | `kubernetes.io/dockerconfigjson` | Container Registry authentication |

The bootstrap script prepares these Secrets using the supplied environment configuration.

Never commit:

- Passwords
- Access tokens
- Actual Secret values
- Kubernetes Secret exports containing credentials
- Local environment files containing secrets

Kubernetes Secrets are not a complete production secrets-management solution.

Stronger secret storage, rotation, and access controls remain future improvements.

## PostgreSQL and Persistent Storage

PostgreSQL runs as a StatefulSet in the `platformforge` namespace.

The GitOps configuration includes:

- PostgreSQL ConfigMap
- PostgreSQL Service
- PostgreSQL StatefulSet
- PostgreSQL PersistentVolumeClaim

### Persistent Volume Configuration

| Property | Value |
|---|---|
| PVC name | `postgres-data` |
| Namespace | `platformforge` |
| Storage class | `standard` |
| Requested capacity | `2Gi` |
| Access mode | `ReadWriteOnce` |

The PostgreSQL PVC manifest includes:

```yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-options: Prune=false
```

This is one of the safeguards intended to prevent accidental pruning of the PVC.

### Persistent Data Safety

**Never delete, replace, or recreate an existing PostgreSQL PVC during routine GitOps synchronization.**

The project has verified two scenarios.

**Existing-cluster integration:**

- An existing PostgreSQL StatefulSet was retained.
- Its existing PVC was preserved.
- Argo CD synchronized the PostgreSQL Application.
- PostgreSQL remained operational.

**Fresh-cluster bootstrap:**

- PostgreSQL resources were deployed in a new cluster.
- The StatefulSet became ready.
- The PVC became Bound.
- PostgreSQL was available before the Platform API synchronization.

These tests demonstrate successful integration under the tested conditions.

They do not replace:

- Database backups
- Restore testing
- Disaster-recovery procedures
- Storage migration planning
- Review of destructive manifest changes

Do not assume that `Prune=false` protects against every possible storage or data-loss scenario.

## Helm Ownership

The Platform API Helm release was originally installed through the Helm CLI during development.

Argo CD now manages the Kubernetes resources rendered from the Helm chart.

The current chart is located at:

```text
infrastructure/helm/platform-api/
```

The Argo CD Application uses the Helm release name:

```text
platform-api
```

Avoid running the following commands against the existing Argo CD-managed deployment without first reviewing resource ownership:

```text
helm uninstall
helm upgrade
helm rollback
```

Direct Helm operations can conflict with the desired state managed by Argo CD.

The intended deployment workflow is declarative and GitOps-driven.

## Database Migrations

PlatformForge uses Alembic for database schema management.

The Platform API Helm chart contains:

```text
templates/migration-job.yaml
```

The migration Job is named:

```text
platform-api-migration
```

It executes:

```text
alembic upgrade head
```

### Argo CD PreSync

The migration Job is configured as an Argo CD PreSync hook.

The intended deployment order is:

```text
PostgreSQL Ready
       |
       v
Platform API Sync
       |
       v
Alembic PreSync Job
       |
       v
Migration Succeeded
       |
       v
FastAPI Deployment
```

The application synchronization is expected to fail rather than proceed normally if the migration hook fails.

### Verified Migration Result

The automated bootstrap test returned:

```text
kind:      Job
name:      platform-api-migration
hookPhase: Succeeded
status:    Synced
message:   Reached expected number of succeeded pods
```

This confirms that the migration Job completed successfully in the tested environment.

### Migration Safety

Database migrations must be reviewed before deployment.

Particular care is required for:

- Destructive schema changes
- Backward compatibility
- Existing application instances
- Failed migrations
- Recovery and rollback procedures

The PreSync hook provides deployment ordering, but it does not automatically make every database migration reversible.

## Verifying a Deployment

All verification commands should target the intended Kubernetes context explicitly.

The following examples use the successfully tested cluster:

```powershell
$testContext = "kind-platformforge-bootstrap-auto"
```

Replace this value when verifying another cluster.

### Verify Argo CD Applications

```powershell
kubectl --context $testContext `
    -n argocd get applications
```

Expected result:

```text
NAME                     SYNC STATUS   HEALTH STATUS
platform-api             Synced        Healthy
platformforge-postgres   Synced        Healthy
platformforge-root       Synced        Healthy
```

### Verify Kubernetes Workloads

```powershell
kubectl --context $testContext `
    -n platformforge get pods,deployments,statefulsets,pvc
```

The verified environment reported:

- Platform API pod: `1/1 Running`
- PostgreSQL pod: `1/1 Running`
- Platform API Deployment: `1/1 Available`
- PostgreSQL StatefulSet: `1/1 Ready`
- PostgreSQL PVC: `Bound`

### Verify GitOps Revision and Migration Job

```powershell
$api = kubectl --context $testContext `
    -n argocd get application platform-api -o json |
    ConvertFrom-Json

[PSCustomObject]@{
    Revision = $api.spec.source.targetRevision
    Sync     = $api.status.sync.status
    Health   = $api.status.health.status
    Result   = $api.status.operationState.phase
}

$api.status.operationState.syncResult.resources |
    Where-Object { $_.kind -eq "Job" } |
    Format-Table kind, name, hookPhase, status, message -AutoSize
```

The verified result was:

```text
Revision: bootstrap-test
Sync:     Synced
Health:   Healthy
Result:   Succeeded
```

The migration Job reported `Succeeded`.

### Verify the API Health Endpoint

Open a separate PowerShell terminal:

```powershell
kubectl --context kind-platformforge-bootstrap-auto `
    -n platformforge port-forward deployment/platform-api 18081:8000
```

In another terminal:

```powershell
Invoke-RestMethod `
    -Uri "http://127.0.0.1:18081/health" `
    -Method Get
```

The verified response was:

```text
status   service
------   -------
healthy  platformforge-api
```

Stop the port-forward using `Ctrl+C`.

## Troubleshooting

### Bootstrap Preflight Failure

Check that the required tools are installed and available in PowerShell:

```powershell
kind version
kubectl version --client
docker version
git --version
```

Ensure Docker Desktop is running with Linux containers enabled.

### Incorrect Kubernetes Context

Always use an explicit context:

```powershell
kubectl --context <target-context> get nodes
```

Do not rely on the current default context when working with multiple clusters.

### Missing Credentials

Verify that the required environment variables are configured in the PowerShell session.

Do not print password or token values.

If Secrets already exist, inspect their names and types without exporting their contents.

### Argo CD Application Not Healthy

Inspect the Application:

```powershell
kubectl --context <target-context> `
    -n argocd get applications
```

For additional details:

```powershell
kubectl --context <target-context> `
    -n argocd describe application platform-api
```

Investigate the reported error before attempting another synchronization.

### PostgreSQL Not Ready

Inspect PostgreSQL resources:

```powershell
kubectl --context <target-context> `
    -n platformforge get statefulset,pods,pvc
```

Do not delete the StatefulSet or PVC as a troubleshooting shortcut.

### Migration Job Failure

Inspect the Platform API Application and its synchronization result.

Check the migration Job or its pod logs if the relevant resources are still available.

Do not repeatedly rerun migrations without understanding the failure and its possible database effects.

### API Not Healthy

Inspect the Deployment:

```powershell
kubectl --context <target-context> `
    -n platformforge get deployment platform-api
```

Inspect the running pods:

```powershell
kubectl --context <target-context> `
    -n platformforge get pods
```

Review application logs and Kubernetes events as appropriate.

## Verified Infrastructure Milestones

### Manual GitOps Integration

The project successfully tested Argo CD management of PostgreSQL and Platform API resources in an existing kind cluster.

Verified outcomes:

- Root and child Applications synchronized successfully.
- PostgreSQL remained ready.
- Existing PostgreSQL persistent storage was retained.
- Alembic migration Job succeeded.
- Platform API deployed successfully.
- HTTP health check passed.

### Automated Fresh-Cluster Bootstrap

The project also successfully tested a new kind cluster created through the bootstrap script.

Verified outcomes:

- Three Kubernetes nodes became Ready.
- Argo CD was installed successfully.
- Required Kubernetes Secrets were prepared.
- The published GitLab integration revision was verified.
- Root and child Applications became Synced and Healthy.
- PostgreSQL StatefulSet became Ready.
- PostgreSQL PVC became Bound.
- Alembic PreSync migration Job succeeded.
- Platform API Deployment became Available.
- HTTP health check returned a healthy response.

These results establish a verified baseline for future infrastructure development.

## Future Improvements

The next infrastructure priorities are:

1. Review and safely integrate the GitOps changes into `main`.
2. Improve CI/CD-to-GitOps container image promotion.
3. Strengthen Kubernetes reliability and recovery procedures.
4. Introduce observability with metrics, logging, tracing, and alerting.
5. Improve secrets management and security controls.
6. Implement database backup and restore procedures.
7. Extend infrastructure automation and operational testing.
8. Introduce Terraform-based AWS infrastructure provisioning.
9. Deploy PlatformForge to Amazon EKS.

The broader PlatformForge roadmap also includes gRPC, Kafka, Strimzi, and the transactional outbox pattern.

## Operational Safety Principles

PlatformForge infrastructure development follows these principles:

- Always identify the target Kubernetes cluster explicitly.
- Treat persistent database storage as protected.
- Avoid destructive synchronization operations without reviewing their effects.
- Separate experimental GitOps changes from the default branch.
- Review changes before merging into branches tracked by active Argo CD installations.
- Do not store credentials in Git.
- Verify database migrations before considering deployments successful.
- Prefer reproducible automation over undocumented manual operations.
- Preserve existing working environments while validating new infrastructure changes.

These principles are particularly important when multiple local kind clusters and GitOps environments are running simultaneously.