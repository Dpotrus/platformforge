#Requires -Version 7.0

<#
.SYNOPSIS
    Bootstrap a disposable PlatformForge kind cluster.

.DESCRIPTION
    Validates required local tooling and protects the original
    PlatformForge Kubernetes cluster from accidental operations.

    Supports:
    - Preflight validation.
    - Creation of a separate kind cluster.
    - Installation of Argo CD v3.5.6.
    - Server-side dry-run of the Argo CD installation manifest.
    - Verification of Kubernetes API readiness.
    - Verification of Argo CD CRDs and component readiness.

    All Kubernetes API operations explicitly specify the
    target Kubernetes context.

    The dry-run validates both the Argo CD CRD Kustomize manifest
    and the full Argo CD installation manifest against an
    existing Kubernetes cluster.

    It does not simulate creating CRDs in an empty cluster.

.PARAMETER ClusterName
    Name of the target kind cluster.

    Default: platformforge-bootstrap-test

    The protected cluster name "platformforge" is rejected.

.PARAMETER Create
    Creates a new kind cluster using infrastructure/kind/cluster.yaml.

    Fails if the target cluster already exists.

.PARAMETER InstallArgoCD
    Installs Argo CD v3.5.6 in the target cluster.

    Can be combined with -Create to install Argo CD immediately
    after creating a new kind cluster.

.PARAMETER ArgoCDDryRun
    Performs Kubernetes server-side dry-run validation of both
    the Argo CD CRD manifest and the full installation manifest.

    Requires -InstallArgoCD and an existing target cluster.

    Cannot be combined with -Create.

.EXAMPLE
    ./infrastructure/scripts/bootstrap-kind.ps1

    Runs preflight validation using the default cluster name.

.EXAMPLE
    ./infrastructure/scripts/bootstrap-kind.ps1 `
        -ClusterName platformforge-bootstrap-fresh `
        -Create

    Creates a new kind cluster without installing Argo CD.

.EXAMPLE
    ./infrastructure/scripts/bootstrap-kind.ps1 `
        -ClusterName platformforge-bootstrap-test `
        -InstallArgoCD `
        -ArgoCDDryRun

    Validates the Argo CD installation manifest against
    the existing test cluster without persisting resources.

.EXAMPLE
    ./infrastructure/scripts/bootstrap-kind.ps1 `
        -ClusterName platformforge-bootstrap-fresh `
        -Create `
        -InstallArgoCD

    Creates a new kind cluster and installs Argo CD.
#>

[CmdletBinding()]
param(
    [string]$ClusterName = "platformforge-bootstrap-test",
    [switch]$Create,
    [switch]$InstallArgoCD,
    [switch]$ArgoCDDryRun,
    [switch]$PreparePlatformForge,
    [switch]$InstallGitOpsRoot,
    [string]$GitOpsRevision = "main",
    [string]$PostgresPasswordEnvVar = "PLATFORMFORGE_POSTGRES_PASSWORD",
    [string]$RegistryUsernameEnvVar = "PLATFORMFORGE_REGISTRY_USERNAME",
    [string]$RegistryTokenEnvVar = "PLATFORMFORGE_REGISTRY_TOKEN"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProtectedClusterName = "platformforge"

if ($ArgoCDDryRun -and -not $InstallArgoCD) {
    throw "-ArgoCDDryRun requires -InstallArgoCD."
}

if ($Create -and $ArgoCDDryRun) {
    throw "-Create and -ArgoCDDryRun cannot be combined."
}

if ($PreparePlatformForge -and $ArgoCDDryRun) { throw "Preparation cannot be combined with dry-run." }
if ($InstallGitOpsRoot -and -not $PreparePlatformForge) { throw "-InstallGitOpsRoot requires -PreparePlatformForge." }
if ($InstallGitOpsRoot -and $Create -and -not $InstallArgoCD) { throw "New GitOps clusters require -InstallArgoCD." }

function Assert-KubernetesContextReady {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$TargetContext,

        [Parameter(Mandatory)]
        [string]$TargetClusterName
    )

    Write-Host "Target Kubernetes context: $TargetContext"

    $availableContexts = @(
        kubectl config get-contexts -o name
    )

    if ($LASTEXITCODE -ne 0) {
        throw "Unable to list Kubernetes contexts."
    }

    if ($TargetContext -notin $availableContexts) {
        throw "Target Kubernetes context does not exist: $TargetContext"
    }

    Write-Host "Kubernetes context found." -ForegroundColor Green

    Write-Host "Verifying kind cluster identity..." -ForegroundColor Cyan

    $expectedContext = "kind-$TargetClusterName"

    if ($TargetContext -cne $expectedContext) {
        throw "Unexpected Kubernetes context for kind cluster: $TargetContext"
    }

    $contextCluster = kubectl config view `
        --raw `
        -o jsonpath="{.contexts[?(@.name=='$TargetContext')].context.cluster}"

    if ($LASTEXITCODE -ne 0) {
        throw "Unable to retrieve Kubernetes context cluster reference."
    }

    if ($contextCluster -cne $expectedContext) {
        throw "Kubernetes context references an unexpected cluster: $contextCluster"
    }

    $kindClusters = @(kind get clusters)

    if ($LASTEXITCODE -ne 0) {
        throw "Unable to list kind clusters during identity verification."
    }

    if ($TargetClusterName -notin $kindClusters) {
        throw "Target kind cluster does not exist: $TargetClusterName"
    }

    $configuredServer = kubectl config view `
        --raw `
        -o jsonpath="{.clusters[?(@.name=='$expectedContext')].cluster.server}"

    if ($LASTEXITCODE -ne 0 -or -not $configuredServer) {
        throw "Unable to retrieve configured Kubernetes API server."
    }

    $kindKubeconfig = @(kind get kubeconfig --name $TargetClusterName)

    if ($LASTEXITCODE -ne 0) {
        throw "Unable to retrieve kind cluster kubeconfig."
    }

    $serverLines = @(
        $kindKubeconfig | Where-Object {
            $_ -match '^\s*server:\s*(\S+)\s*$'
        }
    )

    if ($serverLines.Count -ne 1) {
        throw "Unable to identify a unique API server in kind kubeconfig."
    }

    $kindServer = (
        $serverLines[0] -replace '^\s*server:\s*', ''
    ).Trim()

    if ($configuredServer -cne $kindServer) {
        throw "Kubernetes API server does not match the target kind cluster."
    }

    Write-Host "Kind cluster identity verified." -ForegroundColor Green

    $readinessResponse = kubectl `
        --context $TargetContext `
        --request-timeout=10s `
        get --raw=/readyz

    if ($LASTEXITCODE -ne 0) {
        throw "Kubernetes API server is not ready: $TargetContext"
    }

    if (($readinessResponse | Out-String).Trim() -ne "ok") {
        throw "Unexpected Kubernetes API readiness response."
    }

    Write-Host "Kubernetes API server is ready." -ForegroundColor Green
}

function Install-ArgoCD {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$TargetContext,

        [switch]$DryRun
    )

    $argoCDVersion = "v3.5.6"
    $argoCDNamespace = "argocd"

    $argoCDManifestUrl = (
        "https://raw.githubusercontent.com/argoproj/argo-cd/" +
        "$argoCDVersion/manifests/install.yaml"
    )

    $argoCDCRDKustomizeUrl = (
        "https://github.com/argoproj/argo-cd/manifests/crds" +
        "?ref=$argoCDVersion"
    )

    Write-Host "Argo CD version: $argoCDVersion"
    Write-Host "Argo CD namespace: $argoCDNamespace"
    Write-Host "Installation manifest: $argoCDManifestUrl"

    if ($DryRun) {
        Write-Host "Running Argo CD CRD server-side dry-run..." -ForegroundColor Yellow

        kubectl --context $TargetContext `
            apply `
            --server-side `
            --dry-run=server `
            --field-manager=platformforge-bootstrap `
            -k $argoCDCRDKustomizeUrl

        if ($LASTEXITCODE -ne 0) {
            throw "Argo CD CRD server-side dry-run failed."
        }

        Write-Host "Argo CD CRD server-side dry-run passed." -ForegroundColor Green

        Write-Host "Running Argo CD installation server-side dry-run..." -ForegroundColor Yellow

        kubectl --context $TargetContext `
            apply `
            --server-side `
            --dry-run=server `
            --field-manager=platformforge-bootstrap `
            -n $argoCDNamespace `
            -f $argoCDManifestUrl

        if ($LASTEXITCODE -ne 0) {
            throw "Argo CD installation server-side dry-run failed."
        }

        Write-Host "Argo CD installation server-side dry-run passed." -ForegroundColor Green
        return
    }

    Write-Host "Installing Argo CD $argoCDVersion..." -ForegroundColor Cyan

    $namespaceExists = kubectl `
        --context $TargetContext `
        get namespace $argoCDNamespace `
        --ignore-not-found `
        -o name

    if ($LASTEXITCODE -ne 0) {
        throw "Unable to check Argo CD namespace."
    }

    if (-not $namespaceExists) {
        kubectl --context $TargetContext `
            create namespace $argoCDNamespace

        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create Argo CD namespace."
        }
    }

    Write-Host "Installing Argo CD CRDs..." -ForegroundColor Cyan

    kubectl --context $TargetContext `
        apply `
        --server-side `
        --field-manager=platformforge-bootstrap `
        -k $argoCDCRDKustomizeUrl

    if ($LASTEXITCODE -ne 0) {
        throw "Argo CD CRD installation failed."
    }

    Write-Host "Waiting for Argo CD CRDs..." -ForegroundColor Cyan

    $argoCDCRDs = @(
        "applications.argoproj.io",
        "applicationsets.argoproj.io",
        "appprojects.argoproj.io"
    )

    foreach ($crd in $argoCDCRDs) {
        Write-Host "Checking CRD: $crd"

        kubectl --context $TargetContext `
            wait `
            --for=condition=Established `
            "crd/$crd" `
            --timeout=120s

        if ($LASTEXITCODE -ne 0) {
            throw "Argo CD CRD did not become established: $crd"
        }
    }

    Write-Host "All Argo CD CRDs are established." -ForegroundColor Green

    kubectl --context $TargetContext `
        apply `
        --server-side `
        --field-manager=platformforge-bootstrap `
        -n $argoCDNamespace `
        -f $argoCDManifestUrl

    if ($LASTEXITCODE -ne 0) {
        throw "Argo CD installation failed."
    }

    Write-Host "Argo CD resources applied successfully." -ForegroundColor Green

    Write-Host "Waiting for Argo CD components..." -ForegroundColor Cyan

    $argoCDDeployments = @(
        "argocd-applicationset-controller",
        "argocd-dex-server",
        "argocd-notifications-controller",
        "argocd-redis",
        "argocd-repo-server",
        "argocd-server"
    )

    foreach ($deployment in $argoCDDeployments) {
        Write-Host "Checking deployment: $deployment"

        kubectl --context $TargetContext `
            rollout status "deployment/$deployment" `
            -n $argoCDNamespace `
            --timeout=300s

        if ($LASTEXITCODE -ne 0) {
            throw "Argo CD deployment did not become ready: $deployment"
        }
    }

    Write-Host "Checking StatefulSet: argocd-application-controller"

    kubectl --context $TargetContext `
        rollout status statefulset/argocd-application-controller `
        -n $argoCDNamespace `
        --timeout=300s

    if ($LASTEXITCODE -ne 0) {
        throw "Argo CD application-controller StatefulSet did not become ready."
    }

    Write-Host "All Argo CD components are ready." -ForegroundColor Green
}

function Initialize-PlatformForgeNamespace {
    param([string]$TargetContext)
    $existing = kubectl --context $TargetContext get namespace platformforge --ignore-not-found -o name
    if ($LASTEXITCODE -ne 0) { throw "Unable to check namespace." }
    if (-not $existing) {
        kubectl --context $TargetContext create namespace platformforge | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Unable to create namespace." }
    }
}

function Get-RequiredEnvironmentVariable {
    param([string]$VariableName)
    $value = [Environment]::GetEnvironmentVariable($VariableName, "Process")
    if ([string]::IsNullOrWhiteSpace($value)) { throw "Required environment variable is missing: $VariableName" }
    return $value
}

function Initialize-PlatformForgeSecrets {
    param([string]$TargetContext)
    $missing = @()
    foreach ($name in @("postgres-credentials", "platform-api-db", "gitlab-registry")) {
        $existing = kubectl --context $TargetContext -n platformforge get secret $name --ignore-not-found -o name
        if ($LASTEXITCODE -ne 0) { throw "Cannot inspect Secret: $name" }
        if (-not $existing) { $missing += $name }
    }
    if ($missing.Count -eq 0) { Write-Host "All PlatformForge Secrets already exist."; return }
    $password = $null
    $username = $null
    $token = $null
    if ("postgres-credentials" -in $missing -or "platform-api-db" -in $missing) {
        $password = Get-RequiredEnvironmentVariable -VariableName $PostgresPasswordEnvVar
    }
    if ("gitlab-registry" -in $missing) {
        $username = Get-RequiredEnvironmentVariable -VariableName $RegistryUsernameEnvVar
        $token = Get-RequiredEnvironmentVariable -VariableName $RegistryTokenEnvVar
    }
    foreach ($name in $missing) {
        $type = "Opaque"
        $data = @{}
        switch ($name) {
            "postgres-credentials" { $data.POSTGRES_PASSWORD = $password }
            "platform-api-db" {
                $encoded = [uri]::EscapeDataString($password)
                $data.DATABASE_URL = "postgresql+psycopg://platformforge:${encoded}@postgres:5432/platformforge"
            }
            "gitlab-registry" {
                $type = "kubernetes.io/dockerconfigjson"
                $auth = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("${username}:${token}"))
                $config = @{ auths = @{ "registry.gitlab.com" = @{ username = $username; password = $token; auth = $auth } } }
                $data['.dockerconfigjson'] = ConvertTo-Json -InputObject $config -Depth 10 -Compress
            }
        }
        $manifest = @{ apiVersion = "v1"; kind = "Secret"; metadata = @{ name = $name; namespace = "platformforge" }; type = $type; stringData = $data }
        $again = kubectl --context $TargetContext -n platformforge get secret $name --ignore-not-found -o name
        if ($LASTEXITCODE -ne 0 -or $again) { throw "Secret changed during bootstrap: $name" }
        $json = ConvertTo-Json -InputObject $manifest -Depth 20 -Compress
        $json | kubectl --context $TargetContext -n platformforge create -f - | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Failed to create Secret: $name" }
        Write-Host "Secret created: $name" -ForegroundColor Green
    }
}

function Assert-PublishedGitOpsRevision {
    param([string]$Revision)
    if ($Revision -in @("main", "master") -or [string]::IsNullOrWhiteSpace($Revision)) {
        throw "Full GitOps bootstrap requires an isolated published branch, not main/master."
    }
    if ($Revision -cnotmatch '^[A-Za-z0-9][A-Za-z0-9._/-]*$' -or $Revision.Contains('..') -or $Revision.EndsWith('/')) {
        throw "Invalid GitOps branch name."
    }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "git is required." }
    $repo = "https://gitlab.com/DaxTheTax/platformforge.git"
    $projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
    $branchRef = "refs/heads/$Revision"
    $remote = @(git ls-remote --heads $repo $branchRef)
    if ($LASTEXITCODE -ne 0 -or $remote.Count -ne 1) { throw "Published GitLab branch not found: $Revision" }
    $sha = ($remote[0] -split '\s+')[0]
    if ($sha -notmatch '^[0-9a-f]{40}$') { throw "Invalid remote commit ID." }
    $tempRef = 'refs/platformforge-bootstrap/verification'
    try {
        git -C $projectRoot fetch --no-tags $repo "+${branchRef}:${tempRef}" | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Could not fetch published GitOps branch." }
        $fetched = (git -C $projectRoot rev-parse $tempRef).Trim()
        if ($fetched -cne $sha) { throw "GitLab branch changed during verification; retry." }
        $paths = @(
            'infrastructure/gitops/root.yaml',
            'infrastructure/gitops/applications/kustomization.yaml',
            'infrastructure/gitops/applications/platform-api.yaml',
            'infrastructure/gitops/applications/postgres.yaml',
            'infrastructure/helm/platform-api/templates/migration-job.yaml',
            'infrastructure/kubernetes/postgres/postgres-statefulset.yaml'
        )
        $published = @{}
        foreach ($path in $paths) {
            $content = @(git -C $projectRoot show "${tempRef}:$path") -join "`n"
            if ($LASTEXITCODE -ne 0) { throw "Missing published file: $path" }
            $published[$path] = $content
        }
        $k = $published['infrastructure/gitops/applications/kustomization.yaml']
        if ($k -notmatch "(?m)^\s*-\s*revision=$([regex]::Escape($Revision))\s*$") {
            throw "Published child GitOps revision does not match $Revision."
        }
        if ($k -notmatch 'platform-api.yaml' -or $k -notmatch 'postgres.yaml') { throw "Published Kustomize is incomplete." }
        foreach ($path in @('infrastructure/gitops/applications/platform-api.yaml', 'infrastructure/gitops/applications/postgres.yaml')) {
            if ($published[$path] -match '(?m)^\s*automated\s*:') { throw "Child auto-sync must be disabled: $path" }
        }
        if ($published['infrastructure/helm/platform-api/templates/migration-job.yaml'] -notmatch 'argocd.argoproj.io/hook:\s*PreSync') {
            throw "Published migration hook is missing."
        }
        Write-Host "Published GitOps branch verified: $Revision ($sha)" -ForegroundColor Green
    }
    finally {
        git -C $projectRoot update-ref -d $tempRef 2>$null | Out-Null
    }
}

function Install-PlatformForgeRootApplication {
    param([string]$TargetContext, [string]$GitOpsRevision)
    $path = Join-Path $PSScriptRoot '../gitops/root.yaml'
    $manifest = Get-Content (Resolve-Path $path).Path -Raw
    if ($manifest -notmatch '(?m)^\s*name:\s*platformforge-root\s*$') { throw "Unexpected Root Application." }
    $pattern = '(?m)^(\s*targetRevision:\s*).*$'
    if ([regex]::Matches($manifest, $pattern).Count -ne 1) { throw "Expected one Root targetRevision." }
    $updated = [regex]::Replace($manifest, $pattern, [Text.RegularExpressions.MatchEvaluator] {
        param($m)
        return $m.Groups[1].Value + $GitOpsRevision
    })
    $updated | kubectl --context $TargetContext -n argocd apply -f - | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to apply Root Application." }
}

function Wait-PlatformForgeApplication {
    param([string]$TargetContext, [string]$Name, [string]$Revision, [int]$TimeoutSeconds = 300)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $raw = kubectl --context $TargetContext -n argocd get application $Name --ignore-not-found -o json
        if ($LASTEXITCODE -ne 0) { throw "Cannot inspect Application: $Name" }
        if ($raw) {
            $app = $raw | ConvertFrom-Json
            if ($app.spec.source.targetRevision -cne $Revision) {
                # Root may be updating a pre-existing child; allow reconciliation until timeout.
                Start-Sleep -Seconds 5
                continue
            }
            if ($app.spec.syncPolicy -and $app.spec.syncPolicy.PSObject.Properties["automated"]) { throw "Child Application auto-sync is enabled: $Name" }
            return
        }
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $deadline)
    throw "Application did not appear with expected revision: $Name"
}

function Sync-PlatformForgeApplication {
    param([string]$TargetContext, [string]$Name, [string]$Revision, [int]$TimeoutSeconds = 600)
    $beforeRaw = kubectl --context $TargetContext -n argocd get application $Name -o json
    if ($LASTEXITCODE -ne 0) { throw "Cannot inspect Application: $Name" }
    $before = $beforeRaw | ConvertFrom-Json
    if ($before.spec.source.targetRevision -cne $Revision) { throw "Unexpected revision for $Name" }
    if ($before.spec.syncPolicy -and $before.spec.syncPolicy.PSObject.Properties["automated"]) { throw "Refusing to orchestrate auto-sync Application: $Name" }
    if ($before.PSObject.Properties["operation"] -and $before.operation) { throw "Application already has an active operation: $Name" }
    $patch = @{ operation = @{ sync = @{ revision = $Revision; prune = $false } } } | ConvertTo-Json -Depth 10 -Compress
    kubectl --context $TargetContext -n argocd patch application $Name --type merge -p $patch | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to start sync: $Name" }
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $raw = kubectl --context $TargetContext -n argocd get application $Name -o json
        if ($LASTEXITCODE -ne 0) { throw "Cannot read sync status: $Name" }
        $app = $raw | ConvertFrom-Json
        $state = if ($app.status -and $app.status.PSObject.Properties["operationState"]) { $app.status.operationState } else { $null }
        if ($state -and $state.phase -in @('Failed', 'Error', 'Terminating')) { throw "Sync failed: $Name ($($state.phase))" }
        if ($state -and $state.phase -eq 'Succeeded' -and
            $state.operation.sync.revision -ceq $Revision -and
            $app.status.sync.status -eq 'Synced' -and
            $app.status.health.status -eq 'Healthy') {
            Write-Host "Application synchronized and healthy: $Name" -ForegroundColor Green
            return
        }
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $deadline)
    throw "Timed out waiting for sync: $Name"
}

function Wait-PlatformForgePostgres {
    param([string]$TargetContext)
    kubectl --context $TargetContext -n platformforge rollout status statefulset/postgres --timeout=300s | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "PostgreSQL StatefulSet not ready." }
    Write-Host "PostgreSQL ready." -ForegroundColor Green
}

Write-Host "PlatformForge Bootstrap - Preflight" -ForegroundColor Cyan
Write-Host "Target cluster: $ClusterName"

if ($ClusterName -eq $ProtectedClusterName) {
    throw "Refusing to target the protected cluster: $ProtectedClusterName"
}

if ([string]::IsNullOrWhiteSpace($ClusterName)) {
    throw "ClusterName must not be empty."
}

if ($ClusterName -cnotmatch '^[a-z0-9]([-a-z0-9]*[a-z0-9])?$') {
    throw "ClusterName must contain only lowercase letters, digits, and hyphens, and must start and end with a letter or digit."
}

$requiredCommands = @(
    "kind",
    "kubectl",
    "docker"
)

foreach ($command in $requiredCommands) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $command"
    }

    Write-Host "Found required command: $command" -ForegroundColor Green
}

$dockerStatus = docker info --format '{{.ServerVersion}}'

if ($LASTEXITCODE -ne 0) {
    throw "Docker daemon is not available."
}

Write-Host "Docker server version: $dockerStatus"

$existingClusters = @(kind get clusters)

if ($LASTEXITCODE -ne 0) {
    throw "Unable to list kind clusters."
}

$clusterExists = $ClusterName -in $existingClusters

if ($Create -and $clusterExists) {
    throw "Target kind cluster already exists: $ClusterName"
}

if (($InstallArgoCD -or $PreparePlatformForge) -and -not $Create -and -not $clusterExists) {
    throw "Cannot install Argo CD: target kind cluster does not exist: $ClusterName"
}

Write-Host ""
Write-Host "Preflight checks passed." -ForegroundColor Green
Write-Host "No changes have been made during preflight."

if ($InstallGitOpsRoot) {
    # Validate remote branch before any Kubernetes mutation.
    Assert-PublishedGitOpsRevision -Revision $GitOpsRevision
}

if (-not $Create -and -not $InstallArgoCD -and -not $PreparePlatformForge) {
    Write-Host "Preflight passed; no changes made."
    return
}

if (-not $Create) {
    $targetContext = "kind-$ClusterName"
    Assert-KubernetesContextReady -TargetContext $targetContext -TargetClusterName $ClusterName
    if ($InstallArgoCD) { Install-ArgoCD -TargetContext $targetContext -DryRun:$ArgoCDDryRun }
    if ($PreparePlatformForge) {
        Initialize-PlatformForgeNamespace -TargetContext $targetContext
        Initialize-PlatformForgeSecrets -TargetContext $targetContext
    }
    if ($InstallGitOpsRoot) {
        Install-PlatformForgeRootApplication -TargetContext $targetContext -GitOpsRevision $GitOpsRevision
        Wait-PlatformForgeApplication -TargetContext $targetContext -Name 'platformforge-postgres' -Revision $GitOpsRevision
        Wait-PlatformForgeApplication -TargetContext $targetContext -Name 'platform-api' -Revision $GitOpsRevision
        Sync-PlatformForgeApplication -TargetContext $targetContext -Name 'platformforge-postgres' -Revision $GitOpsRevision
        Wait-PlatformForgePostgres -TargetContext $targetContext
        Sync-PlatformForgeApplication -TargetContext $targetContext -Name 'platform-api' -Revision $GitOpsRevision
    }
    Write-Host "Requested bootstrap stages completed." -ForegroundColor Green
    return
}

if ($InstallGitOpsRoot -and -not $InstallArgoCD) { throw "-Create with GitOps requires -InstallArgoCD." }

$projectRoot = (Resolve-Path (
    Join-Path $PSScriptRoot "../.."
)).Path

$configPath = Join-Path $projectRoot "infrastructure/kind/cluster.yaml"

if (-not (Test-Path $configPath -PathType Leaf)) {
    throw "kind configuration file not found: $configPath"
}

$tempConfigPath = Join-Path (
    [System.IO.Path]::GetTempPath()
) ("platformforge-kind-{0}.yaml" -f [guid]::NewGuid())

$previousContext = kubectl config current-context 2>$null

if ($LASTEXITCODE -ne 0) {
    $previousContext = $null
}

if ($previousContext) {
    Write-Host "Previous Kubernetes context: $previousContext"
}
else {
    Write-Host "No previous Kubernetes context found."
}

try {
    $configContent = Get-Content $configPath -Raw

    $clusterNamePattern = '(?m)^name:[ \t]*platformforge[ \t]*\r?$'
    $replacement = "name: $ClusterName"

    $updatedConfig = [regex]::Replace(
        $configContent,
        $clusterNamePattern,
        $replacement
    )

    if ($updatedConfig -ceq $configContent) {
        throw "Could not update the kind cluster name."
    }

    $expectedNamePattern = "(?m)^name:[ \t]*$([regex]::Escape($ClusterName))[ \t]*\r?$"

    if ($updatedConfig -cnotmatch $expectedNamePattern) {
        throw "Generated kind configuration has an unexpected cluster name."
    }

    Set-Content -Path $tempConfigPath -Value $updatedConfig

    Write-Host "Creating kind cluster: $ClusterName" -ForegroundColor Cyan

    kind create cluster --config $tempConfigPath

    if ($LASTEXITCODE -ne 0) {
        throw "kind cluster creation failed."
    }

    Write-Host "kind cluster created successfully." -ForegroundColor Green
}
finally {
    Remove-Item $tempConfigPath -Force -ErrorAction SilentlyContinue

    if ($previousContext) {
        Write-Host "Restoring Kubernetes context: $previousContext"

        kubectl config use-context $previousContext

        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Unable to restore previous Kubernetes context: $previousContext"
        }
        else {
            Write-Host "Previous Kubernetes context restored." -ForegroundColor Green
        }
    }
}

if ($InstallArgoCD -or $PreparePlatformForge) {
    $targetContext = "kind-$ClusterName"
    Assert-KubernetesContextReady -TargetContext $targetContext -TargetClusterName $ClusterName
    if ($InstallArgoCD) { Install-ArgoCD -TargetContext $targetContext }
    if ($PreparePlatformForge) {
        Initialize-PlatformForgeNamespace -TargetContext $targetContext
        Initialize-PlatformForgeSecrets -TargetContext $targetContext
    }
    if ($InstallGitOpsRoot) {
        Install-PlatformForgeRootApplication -TargetContext $targetContext -GitOpsRevision $GitOpsRevision
        Wait-PlatformForgeApplication -TargetContext $targetContext -Name 'platformforge-postgres' -Revision $GitOpsRevision
        Wait-PlatformForgeApplication -TargetContext $targetContext -Name 'platform-api' -Revision $GitOpsRevision
        Sync-PlatformForgeApplication -TargetContext $targetContext -Name 'platformforge-postgres' -Revision $GitOpsRevision
        Wait-PlatformForgePostgres -TargetContext $targetContext
        Sync-PlatformForgeApplication -TargetContext $targetContext -Name 'platform-api' -Revision $GitOpsRevision
    }
}
Write-Host "PlatformForge bootstrap completed for kind-$ClusterName." -ForegroundColor Green
