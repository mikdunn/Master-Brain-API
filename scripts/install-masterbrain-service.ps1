$ErrorActionPreference = "Stop"

$serviceName = "MasterBrainBridgeAPI"
$projectRoot = "C:\Users\dunnm\Downloads\math-logic-agent"
$runner = "$projectRoot\scripts\run-masterbrain-api.ps1"
$powershellExe = "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"

if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
    Write-Host "nssm not found. Install with: choco install nssm -y"
    exit 1
}

nssm install $serviceName $powershellExe "-NoProfile -ExecutionPolicy Bypass -File $runner"
nssm set $serviceName AppDirectory $projectRoot
nssm set $serviceName Start SERVICE_AUTO_START
nssm set $serviceName DisplayName "Master Brain Bridge API"
nssm set $serviceName Description "Background API bridge for Master Brain queries from Copilot and web clients"

nssm start $serviceName
Write-Host "Service '$serviceName' installed and started."
