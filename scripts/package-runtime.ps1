#Requires -Version 5.1
<#
Empaqueta runtime/ (app + frontend/dist) para distribución y actualizaciones.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$RuntimeDir = Join-Path $Root "runtime"
if (Test-Path $RuntimeDir) {
    Remove-Item $RuntimeDir -Recurse -Force
}
New-Item -ItemType Directory -Path $RuntimeDir | Out-Null

Write-Host "==> Copiando app/"
Copy-Item -Path (Join-Path $Root "app") -Destination (Join-Path $RuntimeDir "app") -Recurse
Get-ChildItem (Join-Path $RuntimeDir "app") -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem (Join-Path $RuntimeDir "app") -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "==> Copiando pyproject.toml y version.json"
Copy-Item (Join-Path $Root "pyproject.toml") (Join-Path $RuntimeDir "pyproject.toml")
Copy-Item (Join-Path $Root "version.json") (Join-Path $RuntimeDir "version.json")
try {
    $sha = (git -C $Root rev-parse HEAD 2>$null).Trim()
    if ($sha) {
        $versionPath = Join-Path $RuntimeDir "version.json"
        $json = Get-Content $versionPath -Raw | ConvertFrom-Json
        $json.commit = $sha
        $json.built_at = (Get-Date).ToUniversalTime().ToString("o")
        $json.repo = "gezpomotorsas/Dashboard-Comercial"
        $json | ConvertTo-Json -Depth 5 | Set-Content $versionPath
        Write-Host "   version.json commit=$($sha.Substring(0, 7))"
    }
} catch {
    Write-Warning "No se pudo escribir commit en version.json (git no disponible)"
}

Write-Host "==> Compilando frontend"
Set-Location (Join-Path $Root "frontend")
if (-not (Test-Path "node_modules")) {
    npm ci
}
$env:VITE_API_BASE_URL = ""
npm run build

Write-Host "==> Copiando frontend/dist"
$DistTarget = Join-Path $RuntimeDir "frontend\dist"
if (Test-Path $DistTarget) {
    Remove-Item $DistTarget -Recurse -Force
}
Copy-Item -Path "dist" -Destination $DistTarget -Recurse -Force

$sampleJs = Get-ChildItem (Join-Path $DistTarget "assets\*.js") -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $sampleJs) {
    throw "frontend/dist/assets/*.js no existe tras el build. Revisa npm run build."
}
Write-Host "   OK: $($sampleJs.Name)"

Set-Location $Root
$ZipPath = Join-Path $Root "runtime.zip"
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path "$RuntimeDir\*" -DestinationPath $ZipPath -Force

Write-Host "==> Listo: runtime/ y runtime.zip"
