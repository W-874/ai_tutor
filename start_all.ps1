param(
    [string]$CondaEnv = "aitutor-backend",
    [string]$ModelProvider = "ollama",
    [string]$OllamaLlmModel = "gemma4:26b",
    [string]$OllamaEmbeddingModel = "nomic-embed-text",
    [string]$OpenAICompatibleLlmHost = "",
    [string]$OpenAICompatibleLlmModel = "",
    [string]$OpenAICompatibleEmbeddingHost = "",
    [string]$OpenAICompatibleEmbeddingModel = "",
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
$flutterRoot = Join-Path $repoRoot "frontend"
$envFile = Join-Path $repoRoot ".env"

if (-not (Test-Path $backendRoot)) { throw "Missing directory: $backendRoot" }
if (-not (Test-Path $flutterRoot)) { throw "Missing directory: $flutterRoot" }

if ([string]::IsNullOrWhiteSpace($ModelProvider)) {
    throw "ModelProvider is required. Use 'ollama' or 'openai-compatible'."
}
$provider = $ModelProvider.Trim().ToLower()
if ($provider -ne "ollama" -and $provider -ne "openai-compatible") {
    throw "Unsupported ModelProvider '$ModelProvider'. Allowed values: ollama, openai-compatible."
}

$requiredCommands = @("docker", "python", "flutter")
if ($provider -eq "ollama") {
    $requiredCommands += "ollama"
}
foreach ($cmd in $requiredCommands) {
    if (-not (Test-CommandExists $cmd)) {
        throw "Command not found: $cmd. Please install and add to PATH."
    }
}

Write-Host "[1/6] Checking Docker..."
Ensure-DockerReady

if ($provider -eq "ollama") {
    Write-Host "[2/6] Checking Ollama and pulling models..."
    Ensure-OllamaReady
    ollama pull $OllamaLlmModel
    ollama pull $OllamaEmbeddingModel
} else {
    Write-Host "[2/6] Using OpenAI-compatible provider (skip Ollama checks)."
}

Write-Host "[3/6] Updating LightRAG .env ..."
$envUpdates = @{
    "LLM_TIMEOUT" = "900"
    "MAX_ASYNC" = "1"
    "MAX_PARALLEL_INSERT" = "1"
    "SUMMARY_LANGUAGE" = "Chinese"
}

if ($provider -eq "ollama") {
    $envUpdates["LLM_BINDING"] = "ollama"
    $envUpdates["LLM_BINDING_HOST"] = "http://host.docker.internal:11434"
    $envUpdates["LLM_MODEL"] = $OllamaLlmModel
    $envUpdates["OLLAMA_LLM_NUM_CTX"] = "8192"
    $envUpdates["OLLAMA_LLM_NUM_PREDICT"] = "1024"
    $envUpdates["EMBEDDING_BINDING"] = "ollama"
    $envUpdates["EMBEDDING_BINDING_HOST"] = "http://host.docker.internal:11434"
    $envUpdates["EMBEDDING_MODEL"] = $OllamaEmbeddingModel
    $envUpdates["EMBEDDING_DIM"] = "768"
} else {
    $llmHost = if (-not [string]::IsNullOrWhiteSpace($OpenAICompatibleLlmHost)) { $OpenAICompatibleLlmHost } else { $env:LLM_BINDING_HOST }
    $llmModel = if (-not [string]::IsNullOrWhiteSpace($OpenAICompatibleLlmModel)) { $OpenAICompatibleLlmModel } else { $env:LLM_MODEL }
    $embeddingHost = if (-not [string]::IsNullOrWhiteSpace($OpenAICompatibleEmbeddingHost)) { $OpenAICompatibleEmbeddingHost } else { $env:EMBEDDING_BINDING_HOST }
    $embeddingModel = if (-not [string]::IsNullOrWhiteSpace($OpenAICompatibleEmbeddingModel)) { $OpenAICompatibleEmbeddingModel } else { $env:EMBEDDING_MODEL }
    $llmApiKey = $env:LLM_BINDING_API_KEY
    $embeddingApiKey = $env:EMBEDDING_BINDING_API_KEY

    if ([string]::IsNullOrWhiteSpace($llmHost)) {
        throw "ModelProvider=openai-compatible requires LLM host. Pass -OpenAICompatibleLlmHost or set env var LLM_BINDING_HOST."
    }
    if ([string]::IsNullOrWhiteSpace($llmModel)) {
        throw "ModelProvider=openai-compatible requires LLM model. Pass -OpenAICompatibleLlmModel or set env var LLM_MODEL."
    }
    if ([string]::IsNullOrWhiteSpace($embeddingHost)) {
        throw "ModelProvider=openai-compatible requires embedding host. Pass -OpenAICompatibleEmbeddingHost or set env var EMBEDDING_BINDING_HOST."
    }
    if ([string]::IsNullOrWhiteSpace($embeddingModel)) {
        throw "ModelProvider=openai-compatible requires embedding model. Pass -OpenAICompatibleEmbeddingModel or set env var EMBEDDING_MODEL."
    }
    if ([string]::IsNullOrWhiteSpace($llmApiKey)) {
        throw "ModelProvider=openai-compatible requires env var LLM_BINDING_API_KEY. Do not hardcode keys in script."
    }
    if ([string]::IsNullOrWhiteSpace($embeddingApiKey)) {
        throw "ModelProvider=openai-compatible requires env var EMBEDDING_BINDING_API_KEY. Do not hardcode keys in script."
    }

    $envUpdates["LLM_BINDING"] = "openai"
    $envUpdates["LLM_BINDING_HOST"] = $llmHost
    $envUpdates["LLM_MODEL"] = $llmModel
    $envUpdates["LLM_BINDING_API_KEY"] = $llmApiKey
    $envUpdates["EMBEDDING_BINDING"] = "openai"
    $envUpdates["EMBEDDING_BINDING_HOST"] = $embeddingHost
    $envUpdates["EMBEDDING_MODEL"] = $embeddingModel
    $envUpdates["EMBEDDING_BINDING_API_KEY"] = $embeddingApiKey
}

Update-EnvFile -FilePath $envFile -Values $envUpdates

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
Write-Host "- Model Provider: $provider"
if ($provider -eq "ollama") {
    Write-Host "- Ollama:   http://127.0.0.1:11434"
} else {
    Write-Host "- LLM Host: $llmHost"
    Write-Host "- Emb Host: $embeddingHost"
}
Write-Host "- LightRAG: http://127.0.0.1:9621"
Write-Host "- Backend:  http://127.0.0.1:8000/docs"
Write-Host "- Flutter:  launched in a new terminal (device=$FlutterDevice)"
