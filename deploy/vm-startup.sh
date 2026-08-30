#!/usr/bin/env bash
# OSIRIS Imhotep — GCP VM startup script (runs once on first boot)
# Installs Docker, docker-compose v2, and sets up the OSIRIS app directory.
set -e

LOG="/var/log/osiris-startup.log"
exec > >(tee -a "$LOG") 2>&1

echo "==> OSIRIS startup: $(date)"

# ── Docker ──────────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "==> Installing Docker (Debian official repo)..."
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl gnupg lsb-release
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
        | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl enable --now docker
    echo "==> Docker installed: $(docker --version)"
else
    echo "==> Docker already present: $(docker --version)"
fi

# ── Firewall (allow HTTP/HTTPS via ufw) ─────────────────────────────────────
if command -v ufw &>/dev/null; then
    ufw allow 80/tcp   # HTTP
    ufw allow 443/tcp  # HTTPS
    ufw allow 8000/tcp # backend direct
    ufw allow 3000/tcp # frontend direct
    ufw --force enable
fi

echo "==> Startup script complete: $(date)"
echo "==> VM ready — run gcp-deploy-local.ps1 from your local machine to push the app."
