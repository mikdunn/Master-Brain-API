$ErrorActionPreference = "Stop"

$serviceName = "MasterBrainBridgeAPI"

if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
    Write-Host "nssm not found."
    exit 1
}

$existingService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if (-not $existingService) {
    Write-Host "Service '$serviceName' is not installed."
    exit 0
}

nssm stop $serviceName
Write-Host "Service '$serviceName' stopped."
