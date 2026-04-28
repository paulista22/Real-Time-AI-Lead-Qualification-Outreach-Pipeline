$ErrorActionPreference = "Stop"

# Always resolve paths relative to this script location.
$dashboardDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $dashboardDir
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$activateScript = Join-Path $projectRoot ".venv\Scripts\Activate.ps1"
$appFile = Join-Path $dashboardDir "app.py"

if (-not (Test-Path $pythonExe)) {
    Write-Host "No se encontro Python del entorno virtual en: $pythonExe" -ForegroundColor Red
    Write-Host "Crea el entorno con: py -3.11 -m venv .venv (en la raiz del proyecto)" -ForegroundColor Yellow
    exit 1
}

if (Test-Path $activateScript) {
    # Optional activation for prompt/env vars in this shell.
    & $activateScript
}

Write-Host "Usando entorno virtual: $pythonExe" -ForegroundColor Green
& $pythonExe -m streamlit run $appFile
