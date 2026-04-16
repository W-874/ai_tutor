param()

$ErrorActionPreference = "Stop"

function Stop-ProjectProcesses {
    param(
        [string]$RepoRoot
    )

    $repoPattern = [Regex]::Escape($RepoRoot)
    $processes = Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and $_.ProcessId -ne $PID
    }

    $targets = $processes | Where-Object {
        ($_.CommandLine -match $repoPattern) -and (
            $_.CommandLine -match 'backend\.main:app' -or
            $_.CommandLine -match '\buvicorn\b' -or
            $_.CommandLine -match 'flutter\s+run' -or
            $_.CommandLine -match 'flutter\s+pub\s+get' -or
            $_.CommandLine -match 'dart-define=API_BASE_URL'
        )
    }

    if (-not $targets) {
        Write-Host "No matching project processes found."
        return
    }

    foreach ($proc in $targets) {
        try {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
            Write-Host "Stopped PID $($proc.ProcessId): $($proc.Name)"
        } catch {
            Write-Warning "Failed to stop PID $($proc.ProcessId): $($proc.Name)"
        }
    }
}

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "[1/2] Stopping project processes (backend/frontend)..."
Stop-ProjectProcesses -RepoRoot $repoRoot

Write-Host "[2/2] Stopping LightRAG containers (docker compose down)..."
if (Get-Command docker -ErrorAction SilentlyContinue) {
    Push-Location $repoRoot
    try {
        docker compose down
    } finally {
        Pop-Location
    }
} else {
    Write-Warning "docker command not found, skipped docker compose down."
}

Write-Host ""
Write-Host "Done. Ollama and Docker Desktop/Engine were not stopped."
