# deploy.ps1 — Full Argus platform deploy
param(
    [switch]$SkipTenancy,
    [switch]$SkipSlo,
    [string]$Namespace = $env:ARGUS_NAMESPACE ?? "argus-system"
)

$ErrorActionPreference = "Stop"

function Step([string]$msg) { Write-Host; Write-Host "==> $msg" -ForegroundColor Cyan }
function Fail([string]$msg) { Write-Error "ERROR: $msg"; exit 1 }

if (-not (Get-Command kubectl   -ErrorAction SilentlyContinue)) { Fail "kubectl not found" }
if (-not (Get-Command helmfile  -ErrorAction SilentlyContinue)) { Fail "helmfile not found" }

# Step 1 — Build in-repo sample image (local Docker; Docker Desktop k8s shares the image store)
Step "[1/4] Building sample service image..."
docker build -t argus/sample-service:1.0.0 deploy/sample-app/app
if ($LASTEXITCODE -ne 0) { Fail "sample image build failed" }

# Step 2 — Helmfile (operators + all argus workloads)
Step "[2/4] Deploying via helmfile (operators -> argus chart)..."
$env:ARGUS_NAMESPACE = $Namespace
helmfile sync
if ($LASTEXITCODE -ne 0) { Fail "helmfile sync failed" }

# Step 3 — etcd maintenance CronJob (not in helm chart)
Step "[3/4] Applying control-plane etcd maintenance job..."
kubectl apply -f deploy/control-plane/etcd-maintenance.yaml -n $Namespace
if ($LASTEXITCODE -ne 0) { Fail "etcd-maintenance apply failed" }

# Step 4 — Post-deploy config (needs running ClickHouse + SigNoz)
if ($SkipTenancy) {
    Step "[4a/4] Skipping tenancy apply (--SkipTenancy)"
} else {
    Step "[4a/4] Applying ClickHouse tenancy policies..."
    $env:ARGUS_NAMESPACE = $Namespace
    bash deploy/tenancy/apply-tenancy.sh
    if ($LASTEXITCODE -ne 0) { Fail "Tenancy apply failed" }
}

if ($SkipSlo) {
    Step "[4b/4] Skipping SLO sync (--SkipSlo)"
} else {
    Step "[4b/4] Syncing SLO alert rules..."
    $env:ARGUS_NAMESPACE = $Namespace
    bash deploy/slo/apply-slo.sh
    if ($LASTEXITCODE -ne 0) { Fail "SLO sync failed" }
}

Write-Host
Write-Host "=================================================================" -ForegroundColor Green
Write-Host "  Argus deploy complete. Access at: http://argus.local"           -ForegroundColor Green
Write-Host "  (Add cluster node IP to hosts: <node-ip>  argus.local)"        -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Green
