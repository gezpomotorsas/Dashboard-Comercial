# Actualiza el código desde GitHub y reconstruye los contenedores (Windows / PowerShell).
# Uso: .\scripts\deploy-from-github.ps1

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

$Branch = if ($env:DEPLOY_BRANCH) { $env:DEPLOY_BRANCH } else { "main" }
$ComposeFile = if ($env:COMPOSE_FILE) { $env:COMPOSE_FILE } else { "docker-compose.yml" }

if (-not (Test-Path $ComposeFile)) {
    throw "No se encontró $ComposeFile en $RootDir"
}

if (-not (Test-Path ".env")) {
    throw "Crea .env a partir de .env.example antes de desplegar."
}

Write-Host "==> Fetch origin ($Branch)"
git fetch origin $Branch

$Local = git rev-parse HEAD
$Remote = git rev-parse "origin/$Branch"

if ($Local -eq $Remote) {
    Write-Host "==> Ya estás en el último commit ($Local). Reconstruyendo contenedores."
} else {
    Write-Host "==> Actualizando $Local -> $Remote"
    git checkout $Branch
    git pull --ff-only origin $Branch
}

Write-Host "==> docker compose build"
docker compose -f $ComposeFile build --pull

Write-Host "==> docker compose up"
docker compose -f $ComposeFile up -d --remove-orphans

docker image prune -f | Out-Null

$Short = git rev-parse --short HEAD
Write-Host "==> Despliegue listo ($Short)"
