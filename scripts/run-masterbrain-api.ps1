$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
Set-Location $projectRoot

function Test-PythonReady {
	param([string]$Py)
	if (-not (Test-Path $Py)) {
		return $false
	}
	& $Py -c "import importlib.util, sys; ok = importlib.util.find_spec('uvicorn') and importlib.util.find_spec('math_logic_agent'); sys.exit(0 if ok else 1)"
	return ($LASTEXITCODE -eq 0)
}

$pythonCandidates = @()
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
	$pythonCandidates += $venvPython
}

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCmd) {
	$pythonCandidates += $pythonCmd.Source
}

$python = $null
foreach ($candidate in $pythonCandidates | Select-Object -Unique) {
	if (Test-PythonReady -Py $candidate) {
		$python = $candidate
		break
	}
}

if (-not $python) {
	throw "No usable Python runtime found. Expected interpreter with uvicorn + math_logic_agent installed. Run scripts/install-masterbrain-service.ps1 to bootstrap dependencies."
}

$hostValue = if ($env:BRIDGE_HOST) { $env:BRIDGE_HOST } else { "127.0.0.1" }
$portValue = if ($env:BRIDGE_PORT) { $env:BRIDGE_PORT } else { "8787" }

& $python -m uvicorn math_logic_agent.api:app --host $hostValue --port $portValue
