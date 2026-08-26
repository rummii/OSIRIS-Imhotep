#!/usr/bin/env bash
# =============================================================================
# OSIRIS Imhotep — one-time Google Cloud bootstrap for Cloud Run + GitHub CI/CD
#
# Run this from Google Cloud Shell (https://cloud.google.com/shell) where gcloud
# is already installed and authenticated. No local installs are needed.
#
#   bash deploy/bootstrap.sh
#
# Overrides (optional):
#   GCP_PROJECT_ID  your GCP project id (defaults to current gcloud project)
#   GCP_REGION      default us-central1
#   GITHUB_REPO     default rummii/OSIRIS-Imhotep
#
# What it creates (idempotent — safe to re-run):
#   1. Artifact Registry  osiris-images
#   2. Cloud SQL Postgres osiris-db (smallest dev tier) + osiris DB + osiris user
#   3. Secret Manager secrets (DeepSeek, Gemini, JWT, superadmin, DB URL, gdoc SA)
#   4. Service accounts: osiris-deploy-sa, osiris-backend-sa, osiris-gdoc-sa
#   5. Workload Identity Federation for GitHub Actions (keyless auth)
#   6. Prints the 3 values to store as GitHub Actions secrets
# =============================================================================
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null | tr -d '\n')}"
REGION="${GCP_REGION:-us-central1}"
GITHUB_REPO="${GITHUB_REPO:-rummii/OSIRIS-Imhotep}"
INSTANCE="osiris-db"
DB_NAME="osiris"
DB_USER="osiris"
ARTIFACT_REPO="osiris-images"
DEPLOY_SA="osiris-deploy-sa"
BACKEND_SA="osiris-backend-sa"
GDOC_SA="osiris-gdoc-sa"
WIF_POOL="osiris-github-pool"
WIF_PROVIDER="osiris-github-provider"

step()  { echo ""; echo "==> $1"; }
fail()  { echo "ERROR: $1" >&2; exit 1; }

if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "(unset)" ]; then
  fail "No project set. Export GCP_PROJECT_ID or run: gcloud config set project <YOUR_PROJECT>"
fi

echo "Project : $PROJECT_ID"
echo "Region  : $REGION"
echo "GitHub  : $GITHUB_REPO"
read -r -p "Continue? [y/N] " ok
[ "${ok,,}" = "y" ] || fail "Aborted."

step "Secret Manager secrets"
secret() { # secret <name> <value>
  local name="$1" value="$2"
  if ! gcloud secrets describe "$name" >/dev/null 2>&1; then
    gcloud secrets create "$name" --replication-policy=automatic >/dev/null
  fi
  printf '%s' "$value" | gcloud secrets versions add "$name" --data-file=- >/dev/null
}

# Prompt for API keys only when they are not already in the environment.
if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  read -r -s -p "DeepSeek API key: " DEEPSEEK_API_KEY; echo
fi
if [ -z "${GEMINI_API_KEY:-}" ]; then
  read -r -s -p "Gemini API key: " GEMINI_API_KEY; echo
fi
[ -n "$DEEPSEEK_API_KEY" ] || fail "DeepSeek API key is required."
[ -n "$GEMINI_API_KEY" ]   || fail "Gemini API key is required."

JWT_SECRET="${JWT_SECRET:-$(openssl rand -hex 32)}"
SUPERADMIN_PASSWORD="${SUPERADMIN_PASSWORD:-$(openssl rand -base64 12 | tr '+/' '-_')}"
DATABASE_URL="postgres+pg8000://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?unix_sock=/cloudsql/${PROJECT_ID}:${REGION}:${INSTANCE}/.s.PGSQL.5432"

secret deepseek-api-key    "$DEEPSEEK_API_KEY"
secret gemini-api-key      "$GEMINI_API_KEY"
secret jwt-secret          "$JWT_SECRET"
secret superadmin-password "$SUPERADMIN_PASSWORD"
secret database-url        "$DATABASE_URL"

step "Google Docs service account + SA key secret"
if ! gcloud iam service-accounts describe "$GDOC_SA@$PROJECT_ID.iam.gserviceaccount.com" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$GDOC_SA" --display-name="OSIRIS Docs exporter"
fi
mkdir -p credentials
gcloud iam service-accounts keys create credentials/osiris-sa.json \
  --iam-account="$GDOC_SA@$PROJECT_ID.iam.gserviceaccount.com" >/dev/null 2>&1 || true
if [ -f credentials/osiris-sa.json ]; then
  if ! gcloud secrets describe gdoc-sa-key >/dev/null 2>&1; then
    gcloud secrets create gdoc-sa-key --replication-policy=automatic >/dev/null
  fi
  gcloud secrets versions add gdoc-sa-key --data-file=credentials/osiris-sa.json >/dev/null
  echo "  SA key saved to credentials/osiris-sa.json AND uploaded to gdoc-sa-key secret."
  echo "  NOTE: delete this local file when done (the secret already holds it)."
fi


step "Deploy + runtime service accounts"
if ! gcloud iam service-accounts describe "$DEPLOY_SA@$PROJECT_ID.iam.gserviceaccount.com" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$DEPLOY_SA" --display-name="OSIRIS GitHub Actions deployer"
fi
if ! gcloud iam service-accounts describe "$BACKEND_SA@$PROJECT_ID.iam.gserviceaccount.com" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$BACKEND_SA" --display-name="OSIRIS backend runtime"
fi

echo "  Granting roles to $DEPLOY_SA ..."
for role in roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$DEPLOY_SA@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="$role" >/dev/null 2>&1 || true
done

echo "  Granting roles to $BACKEND_SA ..."
for role in roles/cloudsql.client roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$BACKEND_SA@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="$role" >/dev/null 2>&1 || true
done

gcloud iam service-accounts add-iam-policy-binding \
  "$BACKEND_SA@$PROJECT_ID.iam.gserviceaccount.com" \
  --role=roles/iam.serviceAccountUser \
  --member="serviceAccount:$DEPLOY_SA@$PROJECT_ID.iam.gserviceaccount.com" >/dev/null

step "Workload Identity Federation (keyless GitHub Actions auth)"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
if ! gcloud iam workload-identity-pools describe "$WIF_POOL" \
    --location=global >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "$WIF_POOL" --location=global >/dev/null
fi
if ! gcloud iam workload-identity-pools providers describe "$WIF_PROVIDER" \
    --location=global --workload-identity-pool="$WIF_POOL" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers create-oidc "$WIF_PROVIDER" \
    --location=global --workload-identity-pool="$WIF_POOL" \
    --issuer-uri=https://token.actions.githubusercontent.com \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition="assertion.repository=='${GITHUB_REPO}' && assertion.ref=='refs/heads/main'"
fi
gcloud iam service-accounts add-iam-policy-binding \
  "$DEPLOY_SA@$PROJECT_ID.iam.gserviceaccount.com" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}/attribute.repository/${GITHUB_REPO}" >/dev/null

step "Done — add these EXACT values as GitHub Actions secrets:"
WIF_PROVIDER_FULL="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WIF_POOL}/providers/${WIF_PROVIDER}"
echo ""
echo "  GitHub repo : https://github.com/${GITHUB_REPO}/settings/secrets/actions"
echo ""
echo "  GCP_PROJECT_ID  = ${PROJECT_ID}"
echo "  GCP_WIF_PROVIDER = ${WIF_PROVIDER_FULL}"
echo "  GCP_DEPLOY_SA    = ${DEPLOY_SA}@${PROJECT_ID}.iam.gserviceaccount.com"
echo ""
echo "  Next: the GitHub Actions workflow builds, pushes to Artifact Registry and"
echo "  deploys both Cloud Run services on every push to main."
echo ""
echo "  Superadmin (backend seeds it on first boot):"
echo "    username: admin"
echo "    password: ${SUPERADMIN_PASSWORD}   (also stored in the superadmin-password secret)"
echo ""
echo "  Tip: gcloud secrets versions access latest --secret=superadmin-password"

