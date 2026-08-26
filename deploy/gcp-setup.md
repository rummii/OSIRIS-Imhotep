# Google Cloud deployment — OSIRIS Imhotep

Recommended architecture: one small Compute Engine VM running Docker Compose
(backend + frontend + Caddy TLS proxy). SQLite and the Google credential file
persist on the VM's disk via bind-mounted volumes.

---

## 1. One-time GCP setup

```bash
# Pick a project (replace IDs below with yours)
gcloud projects create osiris-imhotep --name="OSIRIS Imhotep"
gcloud config set project osiris-imhotep
gcloud auth application-default login   # if not already authenticated

# Enable APIs
gcloud services enable compute.googleapis.com run.googleapis.com artifactregistry.googleapis.com
gcloud services enable docs.googleapis.com drive.googleapis.com
```

## 2. Service Account for Google Docs export (recommended over OAuth token)

```bash
gcloud iam service-accounts create osiris-sa \
    --display-name="OSIRIS Docs exporter"

# Download the key to the project root (becomes ./credentials/osiris-sa.json on the VM)
gcloud iam service-accounts keys create credentials/osiris-sa.json \
    --iam-account=osiris-sa@osiris-imhotep.iam.gserviceaccount.com
```

- Docs/Drive APIs are already enabled (step 1).
- Set `GOOGLE_SERVICE_ACCOUNT_FILE=/app/credentials/osiris-sa.json` in `.env.production`.
- If the doc must be owned by a real Workspace user, enable Domain-wide Delegation and set
  `GOOGLE_DOCS_IMPERSONATE=<user@yourdomain.com>`; otherwise each export shares the doc
  with the engineer's `owner_email` (already supported by the API).

## 3. Static IP + DNS

```bash
gcloud compute addresses create osiris-ip --region us-central1
gcloud compute addresses describe osiris-ip --region us-central1 --format="value(address)"
# Create an A record:  app.yourdomain.com  ->  <that IP>
```

## 4. Firewall rules

```bash
gcloud compute firewall-rules create osiris-http  --allow tcp:80,443 --target-tags osiris-web
gcloud compute firewall-rules create osiris-ssh   --allow tcp:22  --target-tags osiris-web
```

## 5. Provision the VM

```bash
# 2GB (e2-small ~ $13/mo). e2-micro is free-tier but builds must happen elsewhere.
gcloud compute instances create osiris-vm \
    --zone us-central1-a \
    --machine-type e2-small \
    --tags osiris-web \
    --address osiris-ip \
    --image-family ubuntu-2204-lts --image-project ubuntu-os-cloud \
    --boot-disk-size 30GB --boot-disk-type pd-balanced
```

## 6. Build images (NOT on the VM — 1GB micro VMs OOM on `next build`)

Do this locally or in CI, then push to Artifact Registry:

```bash
# Local
docker build -f Dockerfile.frontend -t osiris-frontend .
docker build -f Dockerfile.backend  -t osiris-backend .

# Artifact Registry (adjust region/repo)
gcloud artifacts repositories create osiris --repository-format=docker --location=us-central1
docker tag osiris-frontend us-central1-docker.pkg.dev/osiris-imhotep/osiris/frontend:latest
docker tag osiris-backend  us-central1-docker.pkg.dev/osiris-imhotep/osiris/backend:latest
gcloud auth configure-docker us-central1-docker.pkg.dev
docker push us-central1-docker.pkg.dev/osiris-imhotep/osiris/frontend:latest
docker push us-central1-docker.pkg.dev/osiris-imhotep/osiris/backend:latest
```

> Note: this repo's `docker-compose.yml` uses `build:` contexts (good for local
> testing). On the VM, either sync the full repo there, or switch compose to
> `image:` tags pointing at Artifact Registry.

## 7. Deploy from your local machine folder (no git)

From a PowerShell window **on this machine**, after creating `.env.production`
from `.env.production.example`:

```powershell
powershell -ExecutionPolicy Bypass -File deploy\gcp-deploy-local.ps1 `
    -Project osiris-imhotep -Instance osiris-vm -Zone us-central1-a
```

What the script does:
1. Sets the gcloud project.
2. Stages a clean copy of the folder (excludes `node_modules`, `.venv`, `.next`, `.git`).
3. Verifies `.env.production` exists.
4. Uploads the folder to the VM via `gcloud compute scp`.
5. Builds both images and starts the stack on the VM: `docker compose up -d --build`.

`data/` and `credentials/` travel with the copy and are bind-mounted
(`./data:/app/data`, `./credentials:/app/credentials`), so SQLite users and
the Google SA key persist across redeploys.

> Redeploy anytime by re-running the same command — compose rebuilds and
> restarts containers; volumes keep your data intact.

### cloud-init alternative (one-shot VM setup)

```yaml
#cloud-config
package_update: true
packages: [docker.io, docker-compose-v2]
runcmd:
  - systemctl enable --now docker
```

## 8. Point the Caddyfile at your real domain

Edit `/opt/osiris/Caddyfile` — replace `yourdomain.com` — then:

```bash
cd /opt/osiris && docker compose restart caddy
# Caddy auto-issues Let's Encrypt certs and proxies /api/* -> backend, /* -> frontend
```

## 9. Smoke test

```bash
curl -s https://app.yourdomain.com/api/health
# {"status":"ok", ..., "gdoc_configured":true}

# Login through the proxy (single-origin — no CORS in the browser)
curl -s -X POST https://app.yourdomain.com/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<SUPERADMIN_PASSWORD>"}'
```

Then in the browser: generate a SOW (expect 20–90s), export to Google Docs.

## Rollback / updates

```bash
cd /opt/osiris && docker compose pull && docker compose up -d
# data/ and credentials/ are bind-mounted — they survive container replacement.
```

## Cost reference (us-central1)
- e2-small VM: ~$13/mo (always-on)
- Artifact Registry + Docs/Drive API usage: negligible
- DeepSeek / Gemini: unchanged external API costs
- e2-micro (free tier, 1GB): possible if images are pre-built off-VM
