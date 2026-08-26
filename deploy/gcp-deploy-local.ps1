# OSIRIS Imhotep — deploy from this local folder to a Google Cloud VM (no git).
# Prereqs: gcloud CLI installed + authed, VM + static IP + firewall created
# (see deploy/gcp-setup.md steps 1-5), Docker installed on the VM, and
# .env.production created from .env.production.example.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File deploy\gcp-deploy-local.ps1 `
#       -Project osiris-imhotep -Instance osiris-vm -Zone us-central1-a

param(
    [Parameter(Mandatory = $true)][string]$Project,
    [Parameter(Mandatory = $true)][string]$Instance,
    [string]$Zone = "us-central1-a",
    [string]$StagingDir = (Join-Path $env:TEMP "osiris-deploy")
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot   # project root (deploy\..)

function Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

Step "gcloud: set project"
gcloud config set project $Project

Step "Stage a clean copy (exclude node_modules / .venv / .next / .git)"
if (Test-Path $StagingDir) { Remove-Item $StagingDir -Recurse -Force }
New-Item -ItemType Directory -Path $StagingDir -Force | Out-Null
$rob = @($root, $StagingDir, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NP")
foreach ($d in @("node_modules", ".venv", ".next", ".git", "__pycache__", "caddy_data", "caddy_config")) {
    $rob += "/XD"; $rob += $d
}
robocopy @rob | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed (code $LASTEXITCODE)" }

Step "Verify .env.production exists"
$envFile = Join-Path $root ".env.production"
if (-not (Test-Path $envFile)) {
    throw ".env.production not found. Copy .env.production.example and fill in real values."
}

Step "Upload to VM /tmp/osiris-stage"
gcloud compute scp --recurse --zone $Zone $StagingDir "${Instance}:/tmp/osiris-stage" --compress

Step "Move into /opt/osiris and start the stack"
$remote = "sudo rm -rf /opt/osiris && sudo mkdir -p /opt/osiris && " +
          "sudo cp -a /tmp/osiris-stage/. /opt/osiris/ && sudo rm -rf /tmp/osiris-stage && " +
          "cd /opt/osiris && sudo docker compose up -d --build && sudo docker compose ps"
gcloud compute ssh --zone $Zone $Instance --command $remote

Write-Host ""
Write-Host "Deployed. Health check: https://<your-domain>/api/health" -ForegroundColor Green
Write-Host "(point your A record at the static IP and set the domain in /opt/osiris/Caddyfile first)" -ForegroundColor Yellow
