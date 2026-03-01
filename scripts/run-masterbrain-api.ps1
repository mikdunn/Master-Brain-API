$ErrorActionPreference = "Stop"

Set-Location "C:\Users\dunnm\Downloads\math-logic-agent"

$python = "C:\Users\dunnm\Downloads\math-logic-agent\.venv\Scripts\python.exe"

& $python -m uvicorn math_logic_agent.api:app --host 127.0.0.1 --port 8787
