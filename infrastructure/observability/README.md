# PlatformForge Kubernetes Observability

This directory contains the Kubernetes observability configuration for PlatformForge.

The observability environment runs in a dedicated kind cluster, isolated from the existing PlatformForge GitOps environments.

The configuration is intended for local learning and development, not production deployment.

**Scope:** This README documents the dedicated Kubernetes observability environment. The separate Docker Compose observability stack also provides OpenTelemetry tracing, Grafana Tempo, structured JSON logs, Grafana Alloy, Grafana Loki, and Logs-to-Traces correlation. Those capabilities have been verified locally but are **not documented as installed in this Kubernetes cluster**. See [`../../observability/README.md`](../../observability/README.md).

## Architecture

The Kubernetes observability environment consists of:

- **Prometheus Operator** for managing Prometheus resources.
- **Prometheus** for collecting and querying metrics.
- **Grafana** for visualization.
- **ServiceMonitor** for discovering PlatformForge API metrics.
- **PlatformForge API** exposing Prometheus metrics at `/metrics`.
- **PostgreSQL 17** providing the application's database.

The monitoring stack is installed using the `kube-prometheus-stack` Helm chart.

This Kubernetes environment currently focuses on **metrics**. Centralized logging and distributed tracing are implemented in the separate local Docker Compose environment; extending them to Kubernetes remains future work.

The PlatformForge API is installed using its own Helm chart with observability-specific overrides.

## Environment Isolation

The observability environment uses the following Kubernetes context:

```text
kind-platformforge-observability
```

Namespaces:

| Namespace | Purpose |
|---|---|
| `monitoring` | Prometheus, Grafana and monitoring components |
| `platformforge` | PlatformForge API and PostgreSQL |

All Kubernetes commands must explicitly specify the target context.

The existing PlatformForge GitOps clusters are not part of this installation and must remain unaffected.

**Important:** Do not delete, recreate or modify existing GitOps clusters as part of the observability setup.

## Configuration Files

The observability installation uses files from several project directories:

| File | Purpose |
|---|---|
| `infrastructure/kind/observability/observability.yaml` | Dedicated kind cluster configuration |
| `infrastructure/observability/kube-prometheus-stack/values.yaml` | Monitoring stack Helm values |
| `infrastructure/helm/platform-api/values-observability.yaml` | Platform API observability overrides |
| `infrastructure/helm/platform-api/templates/servicemonitor.yaml` | Prometheus ServiceMonitor |
| `infrastructure/scripts/install-observability-dashboard.ps1` | Grafana dashboard provisioning |
| `observability/grafana/provisioning/dashboards/json/platformforge-api.json` | Shared Grafana dashboard definition |
| `observability/README.md` | Separate local Docker Compose observability stack (metrics, logs, traces) |

The Grafana dashboard JSON is shared between Docker Compose and Kubernetes.

This ensures that the same dashboard can be used in both local observability environments.

## Prerequisites

The verified local environment uses:

- Windows with PowerShell 7
- Docker Desktop
- kind
- kubectl
- Helm
- A locally built `platformforge-api:dev` Docker image

Commands are intended to run from the repository root unless otherwise stated.

Before running Kubernetes commands, verify the available contexts:

```powershell
kubectl config get-contexts
```

Confirm that the intended context exists:

```text
kind-platformforge-observability
```

## 1. Create the Observability Cluster

**Only perform this step when creating a new environment.**

Create the dedicated kind cluster:

```powershell
kind create cluster `
    --name platformforge-observability `
    --config .\infrastructure\kind\observability\observability.yaml
```

Verify the cluster:

```powershell
kubectl --context kind-platformforge-observability get nodes
```

The control-plane node should become Ready.

Do not recreate an existing cluster without reviewing its resources and persistent storage.

## 2. Install kube-prometheus-stack

The monitoring stack is installed using the Prometheus Community Helm chart.

The verified chart version is:

```text
92.14.1
```

### 2.1 Add the Helm Repository

Add the Prometheus Community Helm repository:

```powershell
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts

helm repo update
```

### 2.2 Create the Monitoring Namespace

For a new installation, create the `monitoring` namespace if it does not already exist:

```powershell
kubectl --context kind-platformforge-observability `
    create namespace monitoring `
    --dry-run=client -o yaml |
    kubectl --context kind-platformforge-observability apply -f -
```

### 2.3 Configure Grafana Administrator Credentials

Grafana uses an externally managed Kubernetes Secret for its administrator credentials.

The Secret must exist in the `monitoring` namespace before installing `kube-prometheus-stack`.

The required Secret is named:

```text
grafana-admin-credentials
```

It must contain the following keys:

```text
admin-user
admin-password
```

The Helm values reference this Secret using:

```yaml
grafana:
  adminUser: admin

  admin:
    existingSecret: grafana-admin-credentials
    userKey: admin-user
    passwordKey: admin-password
```

#### Create the Secret for a New Installation

**Run these commands only when preparing a new installation. Do not overwrite credentials in an existing environment.**

Enter a password interactively:

```powershell
$grafanaPassword = Read-Host "Grafana admin password" -AsSecureString
```

Convert it temporarily so that it can be supplied to `kubectl`:

```powershell
$grafanaPasswordPlain = [System.Net.NetworkCredential]::new(
    "",
    $grafanaPassword
).Password
```

Create the Kubernetes Secret:

```powershell
kubectl --context kind-platformforge-observability `
    -n monitoring `
    create secret generic grafana-admin-credentials `
    --from-literal=admin-user=admin `
    "--from-literal=admin-password=$grafanaPasswordPlain"
```

Remove the temporary PowerShell variables:

```powershell
Remove-Variable grafanaPasswordPlain
Remove-Variable grafanaPassword
```

**Security considerations:**

- Never commit administrator passwords to Git.
- Never commit Kubernetes Secret manifests containing actual credentials.
- The password is temporarily held in plaintext memory during Secret creation.
- Supplying the password as a command-line argument can expose it to local process inspection while the command runs.
- Kubernetes Secrets are not encrypted by default merely because their values are stored as Secrets.
- Use stronger secret-management practices for production environments.

The procedure above is intended only for the isolated local learning environment.

### 2.4 Install the Monitoring Stack

Install the monitoring stack:

```powershell
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack `
    --version 92.14.1 `
    --kube-context kind-platformforge-observability `
    --namespace monitoring `
    --create-namespace `
    -f .\infrastructure\observability\kube-prometheus-stack\values.yaml `
    --wait `
    --timeout 10m
```

The installation includes:

- Prometheus Operator
- Prometheus
- Grafana
- Supporting monitoring components

**Alertmanager is disabled** in the documented Kubernetes monitoring configuration. Prometheus alerting rules, routing, and notification delivery have not been verified for this environment.

### 2.5 Verify the Installation

Verify the monitoring pods:

```powershell
kubectl --context kind-platformforge-observability `
    -n monitoring get pods
```

The monitoring components should become Ready.

Verify the Helm release:

```powershell
helm list `
    --kube-context kind-platformforge-observability `
    --namespace monitoring
```

The expected release name is:

```text
monitoring
```

### Important: Existing Installations

The current PlatformForge observability cluster was installed and verified before the external Grafana Secret configuration was introduced.

Its running configuration may therefore differ from the current `values.yaml`.

Do not run `helm upgrade` against the existing cluster solely to apply this documentation change.

Before a future upgrade, review:

- The existing Grafana administrator credentials.
- The existing Helm release values.
- Whether `grafana-admin-credentials` exists.
- The effect of changing the administrator Secret configuration.

The updated values describe the intended configuration for future installations.

## 3. Prepare PostgreSQL

The PlatformForge API requires PostgreSQL.

### 3.1 Create the Application Namespace

For a new installation, create the application namespace if necessary:

```powershell
kubectl --context kind-platformforge-observability `
    create namespace platformforge `
    --dry-run=client -o yaml |
    kubectl --context kind-platformforge-observability apply -f -
```

### 3.2 Prepare Database Secrets

The application requires two Kubernetes Secrets in the `platformforge` namespace:

- `postgres-credentials`
- `platform-api-db`

These Secrets contain the credentials and connection configuration required by PostgreSQL and the PlatformForge API.

The PostgreSQL password and application database connection string must be configured securely before deployment.

Do not commit credentials or actual Secret values to Git.

Before creating Secrets, inspect the existing PostgreSQL manifests to confirm the required Secret keys and connection settings.

### 3.3 Deploy PostgreSQL

After preparing the required Secrets, deploy PostgreSQL:

```powershell
kubectl --context kind-platformforge-observability `
    apply -k .\infrastructure\kubernetes\postgres
```

### 3.4 Verify PostgreSQL

Verify the StatefulSet, pods and persistent storage:

```powershell
kubectl --context kind-platformforge-observability `
    -n platformforge get statefulset,pods,pvc
```

PostgreSQL must be Ready before deploying the PlatformForge API.

**Important:** Never delete or recreate an existing PostgreSQL PVC as part of routine installation or troubleshooting.

The PostgreSQL PVC contains application data and must be treated as persistent state.

## 4. Deploy PlatformForge API

The PlatformForge API is deployed using its existing Helm chart.

### 4.1 Prepare the Docker Image

Build the application image using the project's Docker build configuration.

The expected local image tag is:

```text
platformforge-api:dev
```

Verify that the image exists locally:

```powershell
docker image inspect platformforge-api:dev
```

### 4.2 Load the Image into kind

Load the image into the observability cluster:

```powershell
kind load docker-image platformforge-api:dev `
    --name platformforge-observability
```

This loads the image into the dedicated observability cluster without changing images in other kind clusters.

### 4.3 Install the API

Install the API using its observability-specific Helm values:

```powershell
helm upgrade --install platform-api .\infrastructure\helm\platform-api `
    --kube-context kind-platformforge-observability `
    --namespace platformforge `
    -f .\infrastructure\helm\platform-api\values-observability.yaml `
    --wait `
    --timeout 5m
```

The observability overrides enable the ServiceMonitor:

```yaml
serviceMonitor:
  enabled: true
  interval: 15s
  scrapeTimeout: 10s
  path: /metrics
```

The default Helm values keep ServiceMonitor disabled:

```yaml
serviceMonitor:
  enabled: false
```

This prevents the ServiceMonitor from being created during ordinary API installations unless explicitly enabled.

### 4.4 Verify the Deployment

Verify the application resources:

```powershell
kubectl --context kind-platformforge-observability `
    -n platformforge get deployments,pods,jobs,services,servicemonitors
```

The PlatformForge API should be Ready.

The database migration Job should complete successfully.

The ServiceMonitor should exist in the `platformforge` namespace.

## 5. Verify Prometheus Metrics

The PlatformForge API exposes Prometheus metrics at:

```text
/metrics
```

The Helm chart creates a ServiceMonitor when enabled through `values-observability.yaml`.

Prometheus Operator uses the ServiceMonitor to configure metric collection.

### 5.1 Open Prometheus

Start a Prometheus port-forward:

```powershell
kubectl --context kind-platformforge-observability `
    -n monitoring `
    port-forward svc/monitoring-kube-prometheus-prometheus 9091:9090
```

Open Prometheus:

http://localhost:9091

The Kubernetes Prometheus instance uses local port `9091` to avoid conflicting with the Docker Compose Prometheus instance on port `9090`.

### 5.2 Verify the Scrape Target

In Prometheus, open:

**Status → Target health**

Locate the PlatformForge API ServiceMonitor target.

The expected target is associated with:

```text
serviceMonitor/platformforge/platform-api/0
```

Its status should be:

```text
UP
```

### 5.3 Query Application Metrics

Example PromQL query:

```promql
platformforge_http_requests_total
```

Other available metrics include:

```promql
platformforge_http_request_duration_seconds
```

```promql
platformforge_http_requests_in_progress
```

Metric series may not appear until relevant application traffic has occurred.

## 6. Provision the Grafana Dashboard

The Kubernetes dashboard uses the same JSON definition as the local Docker Compose environment.

The shared dashboard definition is located at:

```text
observability/grafana/provisioning/dashboards/json/platformforge-api.json
```

The Kubernetes installation provisions this dashboard through a labeled ConfigMap.

### 6.1 Install the Dashboard

Run:

```powershell
.\infrastructure\scripts\install-observability-dashboard.ps1 `
    -KubeContext kind-platformforge-observability
```

The script creates or updates the following ConfigMap:

```text
platformforge-api-dashboard
```

Namespace:

```text
monitoring
```

Required label:

```yaml
grafana_dashboard: "1"
```

Grafana's dashboard sidecar discovers the labeled ConfigMap and loads the dashboard automatically.

### 6.2 Verify the ConfigMap

Run:

```powershell
kubectl --context kind-platformforge-observability `
    -n monitoring get configmap platformforge-api-dashboard `
    --show-labels
```

Verify that the ConfigMap has the label:

```text
grafana_dashboard=1
```

### 6.3 Idempotent Provisioning

The provisioning script is designed to be idempotent.

Repeated execution should report:

```text
configmap/platformforge-api-dashboard unchanged
```

when no configuration changes are necessary.

This behavior has been verified in the local observability environment.

The script requires an explicit Kubernetes context but does not restrict execution to the observability cluster.

Always verify the context before running it.

## 7. Access Grafana

Start a Grafana port-forward:

```powershell
kubectl --context kind-platformforge-observability `
    -n monitoring `
    port-forward svc/monitoring-grafana 3001:80
```

Open:

http://localhost:3001

The Kubernetes Grafana instance uses local port `3001` to avoid conflicting with the Docker Compose Grafana instance on port `3000`.

For new installations, sign in using the administrator credentials configured in `grafana-admin-credentials`.

For an existing installation, use its currently configured credentials.

### 7.1 Locate the Dashboard

Dashboard title:

```text
PlatformForge API
```

Dashboard UID:

```text
platformforge-api
```

The dashboard contains four panels:

1. HTTP Request Rate
2. HTTP 5xx Error Rate
3. HTTP P95 Latency
4. HTTP Requests In Progress

### 7.2 Prometheus Datasource

The dashboard uses the Prometheus datasource UID:

```text
prometheus
```

This UID is consistent between the Docker Compose and Kubernetes Grafana environments.

## 8. Generate Test Traffic

Generate application traffic to verify that metrics are collected and displayed.

### 8.1 Start the API Port-Forward

Run:

```powershell
kubectl --context kind-platformforge-observability `
    -n platformforge `
    port-forward svc/platform-api 8001:8000
```

### 8.2 Generate Requests

In another PowerShell terminal, run:

```powershell
1..50 | ForEach-Object {
    Invoke-RestMethod http://localhost:8001/health | Out-Null
    Start-Sleep -Milliseconds 100
}
```

### 8.3 Verify the Results

Check the application metrics in Prometheus.

Example query:

```promql
platformforge_http_requests_total
```

Then open the PlatformForge API dashboard in Grafana.

The request-rate panel should reflect the generated traffic after Prometheus has scraped the new metrics.

Some panels may show zero or no active series when no relevant traffic has occurred.

For example, the HTTP 5xx Error Rate panel may remain at zero if all requests succeed.

## Verified Versions

| Component | Version |
|---|---|
| kube-prometheus-stack Helm chart | 92.14.1 |
| Prometheus Operator application | v0.94.2 |
| PlatformForge API Helm chart | 0.1.0 |

The Helm chart version has been verified against the local installation.

The Grafana `admin.existingSecret`, `userKey` and `passwordKey` settings have also been checked against the Helm chart values for version `92.14.1`.

The updated monitoring values have passed local `helm template` validation.

## Operational Safety

Follow these rules when working with the observability environment:

- Always specify the Kubernetes context explicitly.
- Keep the observability environment isolated from existing GitOps clusters.
- Never delete PostgreSQL PVCs during routine operations.
- Never commit passwords, tokens or database connection strings.
- Review Helm changes before applying upgrades.
- Avoid destructive cleanup commands against existing environments.
- Do not assume that new Helm values are already applied to a running cluster.
- Verify the existing Grafana Secret configuration before upgrading an installed release.
- Do not push infrastructure changes to GitLab without reviewing their potential GitOps impact.

### Development-Only Configuration

The current monitoring configuration is intended for local learning and development, not production deployment.

Prometheus uses temporary storage, and Grafana persistence is disabled.

The local Grafana administrator credentials must not be reused in production.

A production deployment would require additional security controls, persistent storage, backup procedures and appropriate access restrictions.

## Scope and Deployment Status

The local Docker Compose observability stack and this Kubernetes environment are independent:

| Capability | Local Docker Compose | Dedicated Kubernetes observability cluster |
|---|---|---|
| Prometheus metrics and Grafana dashboard | Implemented and verified | Implemented and verified |
| OpenTelemetry traces and Tempo | Implemented and verified | Not deployed/verified in this environment |
| Structured JSON logging, Alloy, and Loki | Implemented and verified | Not deployed/verified in this environment |
| Grafana Logs-to-Traces correlation | Implemented and verified | Not deployed/verified in this environment |
| Alertmanager notifications | Not yet verified | Disabled; not yet verified |
| Argo CD management of observability | Not applicable to local Compose | Not yet implemented |

Do not interpret application-level tracing or logging support as proof that trace or log collection backends are installed in Kubernetes.

## Current Status

The following components have been installed and verified in the dedicated observability cluster:

- Dedicated observability kind cluster
- kube-prometheus-stack
- Prometheus metrics collection
- PlatformForge API ServiceMonitor
- PostgreSQL and PlatformForge API
- Grafana dashboard provisioning through ConfigMap
- Dashboard visualization
- Idempotent PowerShell dashboard installation

The monitoring stack and application are currently installed through Helm and Kubernetes commands rather than managed by Argo CD.

The external Grafana administrator Secret configuration has been added to the local Helm values and validated through `helm template`, but has not been applied to the existing cluster.

Future improvements for **this Kubernetes environment** include:

- Manage the Kubernetes observability stack declaratively through GitOps after reviewing cluster-specific synchronization and secret-handling requirements.
- Deploy and verify OpenTelemetry trace collection and Grafana Tempo in Kubernetes.
- Deploy and verify centralized Kubernetes log collection using Grafana Alloy and Loki.
- Verify Grafana Logs-to-Traces correlation for Kubernetes workloads.
- Introduce Prometheus alerting rules, enable and configure Alertmanager, and test notification delivery.
- Improve secret management and credential rotation.
- Add persistent monitoring storage and operational recovery procedures.

**Verification note:** The statuses above reflect the documented implementation and earlier local verification. They do not assert that the cluster is currently running or that its live Helm values match this file. Inspect the target context and installed release before any changes.
