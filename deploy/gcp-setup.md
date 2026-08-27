# Google Cloud deployment — OSIRIS Imhotep (Cloud Run + GitHub Actions)

Recommended architecture: **two Cloud Run services** (backend FastAPI, frontend
Next.js) deployed automatically from GitHub on every push to `main`. Users
persist in **Cloud SQL (PostgreSQL)**; secrets live in **Secret Manager**; GitHub
authenticates to GCP with **Workload Identity Federation** (keyless — no
service-account JSON stored in GitHub).

```
git push main ─► GitHub Actions (.github/workflows/deploy.yml)
                   ├─ test: pip install + backend smoke/endpoint tests
                   ├─ build & push both images ─► Artifact Registry (us-central1)
                   ├─ deploy backend  ─► Cloud Run "osiris-backend"
                   │     • Cloud SQL via unix socket (/cloudsql/...)
                   │     • secrets: DeepSeek, Gemini, JWT, superadmin pw, DB URL,
                   │       Google SA key (materialised to a file at startup)
                   ├─ deploy frontend ─► Cloud Run "osiris-frontend"
                   │     • BACKEND_URL → backend service URL
                   ├─ CORS_ORIGINS on backend ← frontend URL
                   └─ smoke-test /api/health + frontend /
```

---

## 1. One-time GCP bootstrap (Cloud Shell — 1 run)

Open <https://cloud.google.com/shell> and run:

```bash
bash <(curl -s https://raw.githubusercontent.com/rummii/OSIRIS-Imhotep/main/deploy/bootstrap.sh)
```

or, from a clone of the repo in Cloud Shell:

```bash
bash deploy/bootstrap.sh
```

The script (idempotent) will:

1. Use/create your GCP **project** (`GCP_PROJECT_ID`, billing enabled).
2. Enable the required APIs.
3. Create Artifact Registry repo `osiris-images`.
4. Create Cloud SQL `osiris-db` (Postgres 16, smallest dev tier `db-f1-micro`,
   ~$7–10/mo; falls back to `db-custom-1-3840`) with database `osiris` and
   user `osiris`.
5. Prompt for your **DeepSeek** and **Gemini** API keys, then store everything
   in Secret Manager: `deepseek-api-key`, `gemini-api-key`, `jwt-secret`,
   `superadmin-password`, `database-url`, `gdoc-sa-key`.
6. Create the Google Docs exporter SA (`osiris-gdoc-sa`) and upload its key to
   the `gdoc-sa-key` secret.
7. Create `osiris-deploy-sa` (GitHub deployer) and `osiris-backend-sa` (runtime),
   then Wire Workload Identity Federation for **this** repo's `main` branch.
8. Print the **3 values** to store as GitHub Actions secrets.

> The Cloud SQL instance takes ~5–10 minutes to provision the first time.

## 2. Add the GitHub Actions secrets

Go to **https://github.com/rummii/OSIRIS-Imhotep/settings/secrets/actions**
and add the values printed by the bootstrap:

| Secret name      | Value from bootstrap |
| ---------------- | -------------------- |
| `GCP_PROJECT_ID` | your project id      |
| `GCP_WIF_PROVIDER`| `projects/<number>/locations/global/workloadIdentityPools/osiris-github-pool/providers/osiris-github-provider` |
| `GCP_DEPLOY_SA`  | `osiris-deploy-sa@<project>.iam.gserviceaccount.com` |

## 3. Deploy

That's it — **push to `main`** and the workflow runs test → build → deploy → smoke test.

```bash
git add .
git commit -m "deploy: ..."
git push origin main
```

Watch it at **https://github.com/rummii/OSIRIS-Imhotep/actions**.

## 4. First login

The backend seeds `admin` on first boot. Get the password:

```bash
gcloud secrets versions access latest --secret=superadmin-password
```

Open the frontend URL printed in the workflow log and log in. Change the
password on first login (Account page).

## 5. Costs (us-central1, dev sizing)

| Item                       | Approx. cost        |
| -------------------------- | ------------------- |
| Cloud Run (scales to zero) | $0 when idle        |
| Cloud SQL `db-f1-micro`    | ~$7–10/mo           |
| Artifact Registry + APIs   | negligible          |
| DeepSeek / Gemini          | external API usage  |

## Updating / rollback

- **Update:** push to `main` — workflow rebuilds and redeploys both services.
- **Rollback:** in the Cloud Run console select a previous revision and *Manage traffic*.
- **Scale to zero savings:** both services already have `min-instances=0`; cold
  starts take a few seconds (OpenCV import) — acceptable for development.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Workflow auth fails (`Invalid OIDC token` / permission) | Confirm the 3 secrets exist and the WIF provider condition matches `main`; re-run `deploy/bootstrap.sh` |
| `login` returns 401 after deploy | Backend seeds `admin` only when the users table is empty; if you redeployed with a different `SUPERADMIN_PASSWORD`, access the secret and use that password, or delete rows from the `osiris` DB |
| `/api/health` unreachable | Confirm `--allow-unauthenticated`; check Cloud Run logs for startup errors |
| Google Docs export 503 | Set the `gdoc-sa-key` secret (bootstrap step 6) and redeploy |
| 502 on SOW generation | Check Cloud Run logs: DeepSeek/Gemini keys, or request timeout (>600s) — check `backend` service timeout |

---

# Legacy: single Compute Engine VM + docker-compose (optional, not recommended)

Kept for reference. Old flow: build/upload from this PC with
`deploy/gcp-deploy-local.ps1`, run `docker compose up -d` behind Caddy. Requires
`gcloud` CLI + Docker locally and an always-on ~$13/mo VM. The modern flow above
(Cloud Run) is cheaper, auto-scaling, and fully driven by the GitHub repo.


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

> **⚠️ Service accounts canNOT create Google Docs (verified 2026-08).** The Google Docs API
> rejects `docs.create` with `403 PERMISSION_DENIED` for service accounts in standalone
> (non-Workspace) projects — the SA must belong to a Google Workspace domain. If your project
> `spsasean` is not backed by Workspace, the export endpoint will fail with a clear message.
>
> **Working alternative: user OAuth token.** Run the helper to mint a token for the account
> that should own exported docs, then store it in Secret Manager and point the service at it:
>
> ```bash
> cd backend && .venv\Scripts\python.exe ..\deploy\setup_oauth_token.py
> gcloud secrets create gdoc-oauth-token --data-file=backend/credentials/google-oauth-token.json
> gcloud secrets add-iam-policy-binding gdoc-oauth-token \
>   --member=serviceAccount:890958491914-compute@developer.gserviceaccount.com \
>   --role=roles/secretmanager.secretAccessor
> gcloud run services update osiris-imhotep --region=europe-west1 \
>   --update-secrets=GOOGLE_OAUTH_TOKEN_JSON=gdoc-oauth-token:latest \
>   --update-env-vars=GOOGLE_OAUTH_TOKEN_FILE=/tmp/app-data/oauth-token.json
> ```
> (`main.py` materialises `GOOGLE_OAUTH_TOKEN_JSON` → `GOOGLE_OAUTH_TOKEN_FILE` at startup.)

> **⚠️ Cloud Run storage is ephemeral.** `AUTH_DB_PATH=/tmp/users.db` lives in the instance's
> in-memory `/tmp`, so users, logins and saved SOW documents are reset whenever the service
> scales to zero or recycles an instance. The exported Google Docs are the durable output.
> For durable storage, point `DATABASE_URL` at Cloud SQL (the backend already supports
> `postgres+pg8000://`; `SowStore` auto-uses Postgres when `DATABASE_URL` is set) and attach
> the connection string as a Secret Manager secret.

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
