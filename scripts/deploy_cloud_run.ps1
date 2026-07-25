# Deploy fo-intel-api + fo-intel-web to Cloud Run (Windows PowerShell)
# Usage (from fo-intel/):
#   .\scripts\deploy_cloud_run.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Project = if ($env:GCP_PROJECT) { $env:GCP_PROJECT } else { (gcloud config get-value project 2>$null).Trim() }
$Region = if ($env:GCP_REGION) { $env:GCP_REGION } else { "us-central1" }
if (-not $Project -or $Project -eq "(unset)") {
  throw "Set GCP project: gcloud config set project YOUR_PROJECT"
}

if (-not $env:OPENAI_API_KEY) {
  if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
      if ($_ -match '^\s*OPENAI_API_KEY\s*=\s*(.+)\s*$') {
        $env:OPENAI_API_KEY = $Matches[1].Trim().Trim('"').Trim("'")
      }
    }
  }
}
if (-not $env:OPENAI_API_KEY) { throw "OPENAI_API_KEY required" }

if (-not (Test-Path "data/index/index.faiss")) {
  Write-Host "Building FAISS index..."
  python -m pipeline.build_index
}

$ApiImage = "gcr.io/$Project/fo-intel-api"
$WebImage = "gcr.io/$Project/fo-intel-web"

Write-Host "Building API image $ApiImage ..."
gcloud builds submit --config cloudbuild.api.yaml .

Write-Host "Deploying fo-intel-api ..."
gcloud run deploy fo-intel-api `
  --image $ApiImage `
  --region $Region `
  --allow-unauthenticated `
  --memory 1Gi `
  --set-env-vars "OPENAI_API_KEY=$($env:OPENAI_API_KEY),FO_INDEX_DIR=/app/data/index"

$ApiUrl = (gcloud run services describe fo-intel-api --region $Region --format="value(status.url)").Trim()
Write-Host "API_URL=$ApiUrl"

$WebBuild = @"
steps:
- name: gcr.io/cloud-builders/docker
  args: ['build','-f','Dockerfile','--build-arg','NEXT_PUBLIC_API_URL=$ApiUrl','-t','$WebImage','.']
images: ['$WebImage']
"@
$Tmp = Join-Path $env:TEMP "fo-intel-web-cloudbuild.yaml"
$WebBuild | Set-Content -Path $Tmp -Encoding ascii
Write-Host "Building Web image $WebImage ..."
Push-Location (Join-Path $Root "web")
gcloud builds submit --config $Tmp .
Pop-Location

Write-Host "Deploying fo-intel-web ..."
gcloud run deploy fo-intel-web `
  --image $WebImage `
  --region $Region `
  --allow-unauthenticated `
  --memory 512Mi

$WebUrl = (gcloud run services describe fo-intel-web --region $Region --format="value(status.url)").Trim()
Write-Host "CUSTOMER_URL=$WebUrl"
New-Item -ItemType Directory -Force -Path "data/export" | Out-Null
$WebUrl | Set-Content -Path "data/export/live_url.txt" -Encoding utf8
Write-Host "Done. Customer URL: $WebUrl"
