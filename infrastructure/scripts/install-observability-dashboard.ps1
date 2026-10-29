param(
    [Parameter(Mandatory = $true)]
    [string]$KubeContext,

    [string]$Namespace = "monitoring"
)

$ErrorActionPreference = "Stop"

# Resolve paths relative to this script, not the current terminal directory.
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path

$dashboardPath = Join-Path `
    $projectRoot `
    "observability/grafana/provisioning/dashboards/json/platformforge-api.json"

if (-not (Test-Path $dashboardPath)) {
    throw "Dashboard JSON not found: $dashboardPath"
}

# Ensure the target context exists.
$availableContexts = @(
    kubectl config get-contexts -o name
)

if ($LASTEXITCODE -ne 0) {
    throw "Failed to retrieve Kubernetes contexts."
}

if ($KubeContext -notin $availableContexts) {
    throw "Kubernetes context not found: $KubeContext"
}

Write-Host "Installing PlatformForge dashboard..."
Write-Host "Context:   $KubeContext"
Write-Host "Namespace: $Namespace"

# Generate the ConfigMap without modifying the cluster.
$configMapYaml = kubectl `
    --context $KubeContext `
    -n $Namespace `
    create configmap platformforge-api-dashboard `
    "--from-file=platformforge-api.json=$dashboardPath" `
    --dry-run=client `
    -o yaml

if ($LASTEXITCODE -ne 0) {
    throw "Failed to generate dashboard ConfigMap."
}

# Add the label required by the Grafana dashboard sidecar.
$labeledYaml = $configMapYaml |
    kubectl `
        --context $KubeContext `
        label --local `
        -f - `
        grafana_dashboard=1 `
        -o yaml

if ($LASTEXITCODE -ne 0) {
    throw "Failed to label dashboard ConfigMap."
}

# Create or update the ConfigMap in Kubernetes.
$labeledYaml |
    kubectl `
        --context $KubeContext `
        apply -f -

if ($LASTEXITCODE -ne 0) {
    throw "Failed to apply dashboard ConfigMap."
}

Write-Host "PlatformForge dashboard installed successfully."