param(
    [string]$CondaEnv = "aitutor-backend",
    [string]$OllamaLlmModel = "qwen2.5:7b",
    [string]$OllamaEmbeddingModel = "nomic-embed-text",
    [string]$FlutterDevice = "chrome"
)

$ErrorActionPreference = "Stop"

function Test-CommandExists {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Wait-HttpReady {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 90
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-RestMethod -Uri $Url -TimeoutSec 5 | Out-Null
            return $true
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    return $false
}

function Ensure-DockerReady {
    try {
        docker info | Out-Null
        return
    } catch {
        Write-Host "Docker is not ready. Trying to start Docker Desktop..."
        Start-Process "Docker Desktop" -ErrorAction SilentlyContinue | Out-Null
        $deadline = (Get-Date).AddMinutes(3)
        while ((Get-Date) -lt $deadline) {
            try {
                docker info | Out-Null
                return
            } catch {
                Start-Sleep -Seconds 3
            }
        }
        throw "Docker Desktop startup timeout. Please open it manually and retry."
    }
}

function Ensure-OllamaReady {
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5 | Out-Null
        return
    } catch {
        Write-Host "Ollama is not ready. Trying to run: ollama serve"
        Start-Process "ollama" -ArgumentList "serve" -WindowStyle Minimized -ErrorAction SilentlyContinue | Out-Null
        if (-not (Wait-HttpReady -Url "http://127.0.0.1:11434/api/tags" -TimeoutSeconds 60)) {
            throw "Ollama did not start. Run manually: ollama serve"
        }
    }
}

function Update-EnvFile {
    param(
        [string]$FilePath,
        [hashtable]$Values
    )

    $lines = @()
    if (Test-Path $FilePath) {
        $lines = Get-Content -Path $FilePath
    }

    $map = @{}
    foreach ($line in $lines) {
        if ($line -match '^\s*#' -or $line -notmatch '=') {
            continue
        }
        $idx = $line.IndexOf('=')
        if ($idx -gt 0) {
            $k = $line.Substring(0, $idx).Trim()
            $v = $line.Substring($idx + 1)
            $map[$k] = $v
        }
    }

    foreach ($k in $Values.Keys) {
        $map[$k] = $Values[$k]
    }

    $output = @()
    foreach ($k in $map.Keys | Sort-Object) {
        $output += "$k=$($map[$k])"
    }
    Set-Content -Path $FilePath -Value $output -Encoding UTF8
}

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendRoot = $repoRoot
$flutterRoot = Join-Path $repoRoot "ai_tutor"
$envFile = Join-Path $repoRoot ".env"

if (-not (Test-Path $backendRoot)) { throw "Missing directory: $backendRoot" }
if (-not (Test-Path $flutterRoot)) { throw "Missing directory: $flutterRoot" }

foreach ($cmd in @("ollama", "docker", "python", "flutter")) {
    if (-not (Test-CommandExists $cmd)) {
        throw "Command not found: $cmd. Please install and add to PATH."
    }
}

Write-Host "[1/6] Checking Docker and Ollama..."
Ensure-DockerReady
Ensure-OllamaReady

Write-Host "[2/6] Pulling Ollama models..."
ollama pull $OllamaLlmModel
ollama pull $OllamaEmbeddingModel

Write-Host "[3/6] Updating LightRAG .env ..."
Update-EnvFile -FilePath $envFile -Values @{
    "LLM_BINDING" = "ollama"
    "LLM_BINDING_HOST" = "http://host.docker.internal:11434"
    "LLM_MODEL" = $OllamaLlmModel
    "OLLAMA_LLM_NUM_CTX" = "8192"
    "OLLAMA_LLM_NUM_PREDICT" = "1024"
    "EMBEDDING_BINDING" = "ollama"
    "EMBEDDING_BINDING_HOST" = "http://host.docker.internal:11434"
    "EMBEDDING_MODEL" = $OllamaEmbeddingModel
    "EMBEDDING_DIM" = "768"
    "LLM_TIMEOUT" = "900"
    "MAX_ASYNC" = "1"
    "MAX_PARALLEL_INSERT" = "1"
    "SUMMARY_LANGUAGE" = "Chinese"
}

Write-Host "[4/6] Starting LightRAG (docker compose)..."
Push-Location $repoRoot
docker compose up -d
Pop-Location

if (-not (Wait-HttpReady -Url "http://127.0.0.1:9621/health" -TimeoutSeconds 120)) {
    Write-Warning "LightRAG health check timeout. You can inspect logs manually."
}

Write-Host "[5/6] Starting Python backend..."
$backendCmd = "cd `"$backendRoot`"; "
if (Test-CommandExists "conda") {
    $condaEnvList = (conda env list) -join "`n"
    if ($condaEnvList -match "(^|\s)$CondaEnv(\s|$)") {
        $backendCmd += "conda run -n $CondaEnv python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"
    } else {
        $backendCmd += "python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"
    }
} else {
    $backendCmd += "python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"
}
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd

Write-Host "[6/6] Starting Flutter frontend..."
$flutterCmd = "cd `"$flutterRoot`"; flutter pub get; flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000 -d $FlutterDevice"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $flutterCmd

Write-Host ""
Write-Host "Startup sequence triggered:"
Write-Host "- Repo Root: $repoRoot"
Write-Host "- Ollama:   http://127.0.0.1:11434"
Write-Host "- LightRAG: http://127.0.0.1:9621"
Write-Host "- Backend:  http://127.0.0.1:8000/docs"
Write-Host "- Flutter:  launched in a new terminal (device=$FlutterDevice)"
