$ErrorActionPreference = "Stop"

$serviceName = "MasterBrainBridgeAPI"

if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
    Write-Host "nssm not found."
    exit 1
}

nssm stop $serviceName confirm
nssm remove $serviceName confirm
Write-Host "Service '$serviceName' removed."
