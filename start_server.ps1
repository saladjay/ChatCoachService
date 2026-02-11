# PowerShell script to start the FastAPI server
# Usage: .\start_server.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting ChatCoach API Server" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if .venv exists, if not run uv sync
if (-not (Test-Path ".venv")) {
    Write-Host "Virtual environment not found. Running uv sync..." -ForegroundColor Yellow
    $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
    if ($uvCommand) {
        uv sync
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ Virtual environment created successfully" -ForegroundColor Green
        } else {
            Write-Host "Error: Failed to create virtual environment" -ForegroundColor Red
            Write-Host "Please run 'uv sync' manually" -ForegroundColor Yellow
            exit 1
        }
    } else {
        Write-Host "Error: uv is not installed" -ForegroundColor Red
        Write-Host "Please install uv first: https://docs.astral.sh/uv/getting-started/installation/" -ForegroundColor Yellow
        exit 1
    }
    Write-Host ""
}

# Activate virtual environment if it exists
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & .\.venv\Scripts\Activate.ps1
    Write-Host "✓ Virtual environment activated" -ForegroundColor Green
} else {
    Write-Host "Warning: Virtual environment activation script not found" -ForegroundColor Yellow
    Write-Host "Continuing without virtual environment..." -ForegroundColor Yellow
}

# Check if uvicorn is installed (support both pip and uv)
Write-Host "Checking dependencies..." -ForegroundColor Yellow
$uvicornCheck = python -c "import uvicorn; print('ok')" 2>$null
if ($LASTEXITCODE -ne 0 -or -not $uvicornCheck) {
    Write-Host "Error: uvicorn is not installed" -ForegroundColor Red
    Write-Host "Please run: uv pip install uvicorn" -ForegroundColor Yellow
    Write-Host "Or: pip install uvicorn" -ForegroundColor Yellow
    exit 1
}
Write-Host "✓ uvicorn is installed" -ForegroundColor Green

# Check and start Redis
Write-Host "Checking Redis..." -ForegroundColor Yellow
$redisCliPath = Get-Command redis-cli -ErrorAction SilentlyContinue
if ($redisCliPath) {
    $redisPing = redis-cli ping 2>$null
    if ($redisPing -eq "PONG") {
        Write-Host "✓ Redis is already running" -ForegroundColor Green
    } else {
        Write-Host "Starting Redis server..." -ForegroundColor Yellow
        $redisServerPath = Get-Command redis-server -ErrorAction SilentlyContinue
        if ($redisServerPath) {
            # Start Redis in background
            Start-Process -FilePath "redis-server" -ArgumentList "--port 6379" -WindowStyle Hidden
            Start-Sleep -Seconds 2
            $redisPing = redis-cli ping 2>$null
            if ($redisPing -eq "PONG") {
                Write-Host "✓ Redis started successfully" -ForegroundColor Green
            } else {
                Write-Host "Warning: Failed to start Redis" -ForegroundColor Yellow
                Write-Host "Please start Redis manually: redis-server" -ForegroundColor Yellow
            }
        } else {
            Write-Host "Warning: redis-server not found" -ForegroundColor Yellow
            Write-Host "Please install Redis or start it manually" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "Warning: Redis not found" -ForegroundColor Yellow
    Write-Host "Please install Redis from: https://github.com/microsoftarchive/redis/releases" -ForegroundColor Yellow
    Write-Host "Or use WSL/Docker to run Redis" -ForegroundColor Yellow
}

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "Warning: .env file not found" -ForegroundColor Yellow
    Write-Host "Creating .env from .env.example..." -ForegroundColor Yellow
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "Please edit .env file and add your API keys" -ForegroundColor Yellow
    }
}

# Load .env into current process environment (so ${VAR} in YAML configs works)
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        $line = $_.Trim()
        if (-not $line) { return }
        if ($line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $key = $line.Substring(0, $idx).Trim()
        $val = $line.Substring($idx + 1).Trim()
        if ($val.Length -ge 2) {
            if (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'"))) {
                $val = $val.Substring(1, $val.Length - 2)
            }
        }
        if ($key) { [System.Environment]::SetEnvironmentVariable($key, $val, 'Process') }
    }
}

$scriptArgs = @($args)
if ($scriptArgs -contains "--log-prompt") {
    $env:TRACE_ENABLED = "true"
    $env:TRACE_LOG_LLM_PROMPT = "true"
    if (-not $env:TRACE_LEVEL) {
        $env:TRACE_LEVEL = "debug"
    }
    Write-Host "✓ LLM prompt logging enabled (TRACE_ENABLED=true, TRACE_LOG_LLM_PROMPT=true)" -ForegroundColor Green
    $scriptArgs = $scriptArgs | Where-Object { $_ -ne "--log-prompt" }
}

Write-Host ""
Write-Host "Starting server on http://localhost:8000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""
Write-Host "Available endpoints:" -ForegroundColor Cyan
Write-Host "  - Health check: http://localhost:8000/health" -ForegroundColor White
Write-Host "  - API docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host "  - Screenshot parse: http://localhost:8000/api/v1/chat_screenshot/parse" -ForegroundColor White
Write-Host ""

# Start the server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload @scriptArgs
