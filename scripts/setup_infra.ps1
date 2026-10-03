#Requires -Version 5.1
<#
.SYNOPSIS
    Script PowerShell d'initialisation de l'infrastructure Google Cloud Platform (GCP) pour BiblioBot Paris.

.DESCRIPTION
    Active les APIs nécessaires, crée le registre Artifact Registry, le bucket GCS de session,
    les comptes de service IAM et configure Workload Identity Federation (WIF) pour GitHub Actions.

.PARAMETER ProjectId
    L'identifiant unique du projet Google Cloud (ex: biblio-bot-paris-9730).

.PARAMETER GitHubRepo
    Le nom complet du repository GitHub au format 'proprietaire/depot' (défaut: botalla/telegram-bib-bot).

.PARAMETER Region
    La région GCP cible (défaut: europe-west9).

.EXAMPLE
    .\scripts\setup_infra.ps1 -ProjectId "biblio-bot-paris-9730"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$ProjectId,

    [Parameter(Position = 1)]
    [string]$GitHubRepo = "botalla/telegram-bib-bot",

    [Parameter(Position = 2)]
    [string]$Region = "europe-west9"
)

$ErrorActionPreference = "Stop"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host "🚀 Initialisation Infrastructure GCP pour BiblioBot Paris" -ForegroundColor Cyan
Write-Host "   Projet GCP   : $ProjectId" -ForegroundColor Yellow
Write-Host "   Région       : $Region" -ForegroundColor Yellow
Write-Host "   Repo GitHub  : $GitHubRepo" -ForegroundColor Yellow
Write-Host "==================================================================" -ForegroundColor Cyan

# 1. Sélection du projet actif
Write-Host "`n[1/6] Configuration du projet actif dans gcloud..." -ForegroundColor Green
& gcloud config set project $ProjectId

# 2. Activation des APIs requises
Write-Host "`n[2/6] Activation des APIs Google Cloud (cela peut prendre 1 à 2 minutes)..." -ForegroundColor Green
& gcloud services enable `
    run.googleapis.com `
    artifactregistry.googleapis.com `
    secretmanager.googleapis.com `
    storage.googleapis.com `
    iam.googleapis.com `
    iamcredentials.googleapis.com

# 3. Création du registre Artifact Registry
Write-Host "`n[3/6] Vérification du registre Docker Artifact Registry..." -ForegroundColor Green
$repoExists = $false
try {
    & gcloud artifacts repositories describe biblio-bot-repo --location=$Region 2>$null
    if ($LASTEXITCODE -eq 0) { $repoExists = $true }
} catch {
    $repoExists = $false
}

if (-not $repoExists) {
    Write-Host "Création du dépôt Artifact Registry 'biblio-bot-repo'..." -ForegroundColor Gray
    & gcloud artifacts repositories create biblio-bot-repo `
        --repository-format=docker `
        --location=$Region `
        --description="Depot Docker pour BiblioBot Paris"
} else {
    Write-Host "Le dépôt Artifact Registry 'biblio-bot-repo' existe déjà." -ForegroundColor Gray
}

# 4. Création du bucket de sessions GCS
$BucketName = "${ProjectId}-bibbot-state"
Write-Host "`n[4/6] Vérification du bucket Cloud Storage 'gs://$BucketName'..." -ForegroundColor Green
$bucketExists = $false
try {
    & gcloud storage buckets describe "gs://$BucketName" 2>$null
    if ($LASTEXITCODE -eq 0) { $bucketExists = $true }
} catch {
    $bucketExists = $false
}

if (-not $bucketExists) {
    Write-Host "Création du bucket gs://$BucketName..." -ForegroundColor Gray
    & gcloud storage buckets create "gs://$BucketName" `
        --location=$Region `
        --uniform-bucket-level-access
} else {
    Write-Host "Le bucket gs://$BucketName existe déjà." -ForegroundColor Gray
}

# 5. Création des Service Accounts & Permissions IAM
Write-Host "`n[5/6] Configuration des comptes de service (IAM)..." -ForegroundColor Green

$AppSaName = "biblio-bot-sa"
$AppSaEmail = "${AppSaName}@${ProjectId}.iam.gserviceaccount.com"
$DeployerSaName = "github-deployer-sa"
$DeployerSaEmail = "${DeployerSaName}@${ProjectId}.iam.gserviceaccount.com"

# Compte applicatif Cloud Run
try {
    & gcloud iam service-accounts describe $AppSaEmail 2>$null
} catch {
    Write-Host "Création du compte applicatif $AppSaName..." -ForegroundColor Gray
    & gcloud iam service-accounts create $AppSaName --display-name="BiblioBot App SA"
}

# Compte CI/CD GitHub Actions
try {
    & gcloud iam service-accounts describe $DeployerSaEmail 2>$null
} catch {
    Write-Host "Création du compte de déploiement $DeployerSaName..." -ForegroundColor Gray
    & gcloud iam service-accounts create $DeployerSaName --display-name="GitHub Deployer SA"
}

Write-Host "Attribution des rôles de sécurité (moindre privilège)..." -ForegroundColor Gray
& gcloud projects add-iam-policy-binding $ProjectId --member="serviceAccount:${AppSaEmail}" --role="roles/secretmanager.secretAccessor" --quiet
& gcloud storage buckets add-iam-policy-binding "gs://${BucketName}" --member="serviceAccount:${AppSaEmail}" --role="roles/storage.objectAdmin" --quiet

& gcloud projects add-iam-policy-binding $ProjectId --member="serviceAccount:${DeployerSaEmail}" --role="roles/run.admin" --quiet
& gcloud projects add-iam-policy-binding $ProjectId --member="serviceAccount:${DeployerSaEmail}" --role="roles/artifactregistry.writer" --quiet
& gcloud iam service-accounts add-iam-policy-binding $AppSaEmail --member="serviceAccount:${DeployerSaEmail}" --role="roles/iam.serviceAccountUser" --quiet

# 6. Configuration Workload Identity Federation (WIF) pour GitHub Actions
Write-Host "`n[6/6] Configuration de Workload Identity Federation (WIF)..." -ForegroundColor Green

$PoolName = "github-pool"
$ProviderName = "github-provider"

try {
    & gcloud iam workload-identity-pools describe $PoolName --location="global" 2>$null
} catch {
    Write-Host "Création du Workload Identity Pool '$PoolName'..." -ForegroundColor Gray
    & gcloud iam workload-identity-pools create $PoolName --location="global" --display-name="GitHub Pool"
}

$WifPoolResource = (& gcloud iam workload-identity-pools describe $PoolName --location="global" --format="value(name)").Trim()

try {
    & gcloud iam workload-identity-pools providers describe $ProviderName --location="global" --workload-identity-pool=$PoolName 2>$null
} catch {
    Write-Host "Création du Provider OIDC '$ProviderName' lié à $GitHubRepo..." -ForegroundColor Gray
    & gcloud iam workload-identity-pools providers create-oidc $ProviderName `
        --location="global" `
        --workload-identity-pool=$PoolName `
        --issuer-uri="https://token.actions.githubusercontent.com" `
        --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" `
        --attribute-condition="assertion.repository == '${GitHubRepo}'"
}

$WifProviderResource = (& gcloud iam workload-identity-pools providers describe $ProviderName --location="global" --workload-identity-pool=$PoolName --format="value(name)").Trim()

Write-Host "Liaison du compte de service GitHub Actions au Provider WIF..." -ForegroundColor Gray
& gcloud iam service-accounts add-iam-policy-binding $DeployerSaEmail `
    --role="roles/iam.workloadIdentityUser" `
    --member="principalSet://iam.googleapis.com/${WifPoolResource}/attribute.repository/${GitHubRepo}" --quiet

Write-Host "`n==================================================================" -ForegroundColor Green
Write-Host "🎉 INFRASTRUCTURE INITIALISÉE AVEC SUCCÈS !" -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green
Write-Host "`nCopiez ces valeurs dans GitHub (Settings > Secrets and variables > Actions) :" -ForegroundColor Yellow

Write-Host "`n--- VARIABLES (onglet Variables) ---" -ForegroundColor Cyan
Write-Host "GCP_PROJECT_ID   : $ProjectId"
Write-Host "GCP_REGION       : $Region"
Write-Host "GCS_BUCKET_NAME  : $BucketName"
Write-Host "ALLOWED_USER_IDS : (Vos identifiants Telegram séparés par virgule, ex: 12345678)"

Write-Host "`n--- SECRETS (onglet Secrets) ---" -ForegroundColor Cyan
Write-Host "WIF_PROVIDER         : $WifProviderResource"
Write-Host "WIF_SERVICE_ACCOUNT  : $DeployerSaEmail"
Write-Host "TELEGRAM_BOT_TOKEN   : (Le jeton BotFather)"
Write-Host "TELEGRAM_WEBHOOK_SECRET : (Une chaîne secrète aléatoire de votre choix)"
Write-Host "==================================================================" -ForegroundColor Green
