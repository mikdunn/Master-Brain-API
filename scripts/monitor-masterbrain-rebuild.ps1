param(
    [string]$ProjectRoot = "C:\Users\dunnm\Dropbox\Apps\Master-Brain-API",
    [string]$IndexPath = "C:\Users\dunnm\Dropbox\Apps\Master-Brain-API\data\master_brain_index.pkl",
    [string]$CheckpointPath = "C:\Users\dunnm\Dropbox\Apps\Master-Brain-API\data\master_brain_checkpoint.json",
    [string]$LogPath = "C:\Users\dunnm\Dropbox\Apps\Master-Brain-API\data\logs\dropbox_rebuild.log",
    [int]$RefreshSeconds = 3,
    [int]$TailLines = 25,
    [switch]$Once
)

$ErrorActionPreference = "Stop"

function Get-BuildProcesses {
    $procs = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq "python.exe" -and
        $_.CommandLine -match "build-master-brain|math_logic_agent.cli" -and
        $_.CommandLine -match [regex]::Escape($ProjectRoot)
    }
    return $procs
}

function Render-Snapshot {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "============================================================"
    Write-Host "Master Brain Rebuild Monitor  |  $timestamp"
    Write-Host "ProjectRoot:   $ProjectRoot"
    Write-Host "IndexPath:     $IndexPath"
    Write-Host "Checkpoint:    $CheckpointPath"
    Write-Host "Log:           $LogPath"
    Write-Host "============================================================"

    $buildProcs = Get-BuildProcesses
    if ($buildProcs) {
        Write-Host "\n[build process] RUNNING" -ForegroundColor Yellow
        $buildProcs |
            Select-Object ProcessId, ParentProcessId, CommandLine |
            Format-Table -Wrap -AutoSize |
            Out-String |
            Write-Host
    }
    else {
        Write-Host "\n[build process] NOT RUNNING" -ForegroundColor Green
    }

    if (Test-Path $IndexPath) {
        $idx = Get-Item $IndexPath
        Write-Host "[index file] PRESENT" -ForegroundColor Green
        Write-Host "  Size:       $($idx.Length) bytes"
        Write-Host "  LastWrite:  $($idx.LastWriteTime)"
    }
    else {
        Write-Host "[index file] MISSING" -ForegroundColor Red
    }

    if (Test-Path $CheckpointPath) {
        try {
            $cp = Get-Content $CheckpointPath -Raw | ConvertFrom-Json
            Write-Host "[checkpoint] FOUND" -ForegroundColor Green
            Write-Host "  status:                 $($cp.status)"
            Write-Host "  processed_changed_files: $($cp.processed_changed_files)"
            Write-Host "  modules_built:          $($cp.modules_built)"
            Write-Host "  failed_files:           $($cp.failed_files)"
            Write-Host "  chunks_created:         $($cp.chunks_created)"
            Write-Host "  updated_at:             $($cp.updated_at)"
        }
        catch {
            Write-Host "[checkpoint] unreadable JSON: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
    else {
        Write-Host "[checkpoint] missing" -ForegroundColor Red
    }

    if (Test-Path $LogPath) {
        Write-Host "\n[log tail] last $TailLines lines"
        Get-Content $LogPath -Tail $TailLines | Out-String | Write-Host
    }
    else {
        Write-Host "\n[log tail] log file missing"
    }
}

if ($Once) {
    Render-Snapshot
    exit 0
}

Write-Host "Starting live monitor. Press Ctrl+C to stop." -ForegroundColor Cyan
while ($true) {
    Clear-Host
    Render-Snapshot
    Start-Sleep -Seconds $RefreshSeconds
}
