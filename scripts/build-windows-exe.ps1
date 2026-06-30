#Requires -Version 5.1
<#
Genera el ejecutable Windows en dist/DashboardComercial/
Requisitos: Python 3.12+, pip install -e ".[launcher]"
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Stop-DashboardProcesses {
    Get-Process -Name "DashboardComercial" -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 1
}

function Clear-DistOutput {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    Write-Host "==> Limpiando $Path"
    Stop-DashboardProcesses
    try {
        Remove-Item $Path -Recurse -Force -ErrorAction Stop
    } catch {
        Write-Warning "No se pudo borrar dist (archivo en uso). Cierra DashboardComercial.exe y cualquier ventana en esa carpeta."
        Write-Warning "OneDrive también puede bloquear archivos; pausa la sync un momento si persiste."
        throw
    }
}

Write-Host "==> Instalando dependencias"
python -m pip install -e ".[launcher]"

Write-Host "==> Empaquetando runtime"
& (Join-Path $PSScriptRoot "package-runtime.ps1")

$OutDir = Join-Path $Root "dist\DashboardComercial"
Clear-DistOutput -Path $OutDir

Write-Host "==> PyInstaller"
python -m PyInstaller DashboardComercial.spec --noconfirm
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller falló (código $LASTEXITCODE). Cierra el .exe si está abierto e intenta de nuevo."
}

Copy-Item (Join-Path $Root "runtime") (Join-Path $OutDir "runtime") -Recurse -Force
Copy-Item (Join-Path $Root ".env.example") (Join-Path $OutDir ".env.example") -Force
New-Item -ItemType Directory -Path (Join-Path $OutDir "data") -Force | Out-Null

Write-Host ""
Write-Host "==> Ejecutable listo en:"
Write-Host "   $OutDir\DashboardComercial.exe"
Write-Host ""
Write-Host "Comparte toda la carpeta dist/DashboardComercial (exe + runtime + data)."
