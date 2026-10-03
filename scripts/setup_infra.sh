#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Script d'Initialisation de l'Infrastructure GCP pour BiblioBot Paris
# ==============================================================================

PROJECT_ID="${1:-}"
GITHUB_REPO="${2:-botalla/telegram-bib-bot}"
REGION="${3:-europe-west9}"

if [[ -z "$PROJECT_ID" ]]; then
    echo "Usage: $0 <PROJECT_ID> [GITHUB_REPO] [REGION]"
    echo "Exemple: $0 mon-bibliobot-paris botalla/telegram-bib-bot europe-west9"
    exit 1
fi

echo "==> Configuration du projet : $PROJECT_ID ($REGION)..."
gcloud config set project "$PROJECT_ID"

echo "==> 1. Activation des APIs GCP..."
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    storage.googleapis.com \
    iam.googleapis.com \
    iamcredentials.googleapis.com

echo "==> 2. Création du registre Artifact Registry..."
gcloud artifacts repositories describe biblio-bot-repo --location="$REGION" &>/dev/null || \
gcloud artifacts repositories create biblio-bot-repo \
    --repository-format=docker \
    --location="$REGION" \
    --description="Dépôt Docker pour BiblioBot Paris"

echo "==> 3. Création du bucket de sessions GCS..."
BUCKET_NAME="${PROJECT_ID}-bibbot-state"
gcloud storage buckets describe "gs://${BUCKET_NAME}" &>/dev/null || \
gcloud storage buckets create "gs://${BUCKET_NAME}" \
    --location="$REGION" \
    --uniform-bucket-level-access

echo "==> 4. Création des Service Accounts..."
APP_SA="biblio-bot-sa@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud iam service-accounts describe "$APP_SA" &>/dev/null || \
gcloud iam service-accounts create biblio-bot-sa --display-name="BiblioBot App SA"

GH_SA="github-deployer-sa@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud iam service-accounts describe "$GH_SA" &>/dev/null || \
gcloud iam service-accounts create github-deployer-sa --display-name="GitHub Deployer SA"

echo "==> 5. Attribution des permissions IAM..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:${APP_SA}" --role="roles/secretmanager.secretAccessor" --quiet
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" --member="serviceAccount:${APP_SA}" --role="roles/storage.objectAdmin" --quiet

gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:${GH_SA}" --role="roles/run.admin" --quiet
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:${GH_SA}" --role="roles/artifactregistry.writer" --quiet
gcloud iam service-accounts add-iam-policy-binding "$APP_SA" --member="serviceAccount:${GH_SA}" --role="roles/iam.serviceAccountUser" --quiet

echo "==> 6. Configuration WIF pour GitHub Actions..."
gcloud iam workload-identity-pools describe "github-pool" --location="global" &>/dev/null || \
gcloud iam workload-identity-pools create "github-pool" --location="global" --display-name="GitHub Pool"

WIF_POOL_NAME=$(gcloud iam workload-identity-pools describe "github-pool" --location="global" --format="value(name)")

gcloud iam workload-identity-pools providers describe "github-provider" --location="global" --workload-identity-pool="github-pool" &>/dev/null || \
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
    --location="global" \
    --workload-identity-pool="github-pool" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository == '${GITHUB_REPO}'"

gcloud iam service-accounts add-iam-policy-binding "$GH_SA" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/${WIF_POOL_NAME}/attribute.repository/${GITHUB_REPO}" --quiet

echo "=================================================================="
echo "✅ Infrastructure initialisée avec succès !"
echo "Secrets GitHub à renseigner :"
echo "  - GCP_PROJECT_ID: $PROJECT_ID"
echo "  - GCP_REGION: $REGION"
echo "  - WIF_PROVIDER: $(gcloud iam workload-identity-pools providers describe "github-provider" --location="global" --workload-identity-pool="github-pool" --format="value(name)")"
echo "  - WIF_SERVICE_ACCOUNT: $GH_SA"
echo "  - GCS_BUCKET_NAME: $BUCKET_NAME"
echo "=================================================================="
