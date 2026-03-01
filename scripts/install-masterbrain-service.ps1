$ErrorActionPreference = "Stop"

$serviceName = "MasterBrainBridgeAPI"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
$runner = Join-Path $projectRoot "scripts\run-masterbrain-api.ps1"
$powershellExe = "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
$logsDir = Join-Path $projectRoot "data\logs"
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$bridgeKey = "master-brain-bridge-local"
$defaultIndex = Join-Path $projectRoot "data\master_brain_index.pkl"

if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
}

if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
    Write-Host "nssm not found. Install with: choco install nssm -y"
    exit 1
}

# Bootstrap Python runtime in workspace venv (one-time for this device/workspace)
if (-not (Test-Path $venvPython)) {
    $sysPy = Get-Command python -ErrorAction SilentlyContinue
    if (-not $sysPy) {
        throw "Python not found on PATH. Install Python 3.11+ before installing service."
    }
    & $sysPy.Source -m venv (Join-Path $projectRoot ".venv")
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -e $projectRoot

$existingService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if (-not $existingService) {
    nssm install $serviceName $powershellExe "-NoProfile -ExecutionPolicy Bypass -File `"$runner`""
}

nssm set $serviceName Application $powershellExe
nssm set $serviceName AppParameters "-NoProfile -ExecutionPolicy Bypass -File `"$runner`""
nssm set $serviceName AppDirectory $projectRoot
nssm set $serviceName Start SERVICE_AUTO_START
nssm set $serviceName AppExit Default Restart
nssm set $serviceName AppRestartDelay 5000
nssm set $serviceName AppStdout (Join-Path $logsDir "bridge-stdout.log")
nssm set $serviceName AppStderr (Join-Path $logsDir "bridge-stderr.log")
nssm set $serviceName AppRotateFiles 1
nssm set $serviceName AppRotateOnline 1
nssm set $serviceName AppRotateSeconds 86400
nssm set $serviceName AppRotateBytes 10485760
nssm set $serviceName AppEnvironmentExtra @(
    "BRIDGE_WORKSPACE_ROOT=$projectRoot"
    "BRIDGE_DEFAULT_INDEX_PATH=$defaultIndex"
    "BRIDGE_API_KEY=$bridgeKey"
)
nssm set $serviceName DisplayName "Master Brain Bridge API"
nssm set $serviceName Description "Background API bridge for Master Brain queries from Copilot and web clients"

nssm start $serviceName
Write-Host "Service '$serviceName' installed and started."
