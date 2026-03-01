$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
Set-Location $projectRoot

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
	$python = $venvPython
} else {
	$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
	if (-not $pythonCmd) {
		throw "Python executable not found. Install Python or create .venv at $projectRoot\.venv"
	}
	$python = $pythonCmd.Source
}

$hostValue = if ($env:BRIDGE_HOST) { $env:BRIDGE_HOST } else { "127.0.0.1" }
$portValue = if ($env:BRIDGE_PORT) { $env:BRIDGE_PORT } else { "8787" }

& $python -m uvicorn math_logic_agent.api:app --host $hostValue --port $portValue
