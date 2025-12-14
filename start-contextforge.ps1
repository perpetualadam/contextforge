# ContextForge Startup Script for Windows PowerShell
# Run this script to start all ContextForge services locally

param(
    [switch]$Docker,
    [switch]$StopAll,
    [switch]$Status,
    [int]$ApiPort = 8080,
    [int]$VectorPort = 8001
)

$ProjectRoot = $PSScriptRoot
if (-not $ProjectRoot) { $ProjectRoot = Get-Location }

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "   ContextForge Startup Script" -ForegroundColor Cyan  
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Function to check if a port is in use
function Test-Port {
    param([int]$Port)
    $result = netstat -aon | findstr ":$Port " | findstr "LISTENING"
    return $null -ne $result
}

# Function to check service health (uses curl for reliability)
function Test-ServiceHealth {
    param([string]$Url, [string]$Name)
    try {
        $result = curl.exe -s -o NUL -w "%{http_code}" --connect-timeout 10 --max-time 15 $Url 2>$null
        if ($result -eq "200") {
            Write-Host "  [OK] $Name is healthy" -ForegroundColor Green
        } elseif ($result -match "^\d+$") {
            Write-Host "  [?] $Name returned status $result" -ForegroundColor Yellow
        } else {
            Write-Host "  [X] $Name is not responding" -ForegroundColor Red
        }
    } catch {
        Write-Host "  [X] $Name connection failed" -ForegroundColor Red
    }
}

# Status check
if ($Status) {
    Write-Host "Checking service status..." -ForegroundColor Yellow
    Write-Host ""
    
    # Check Ollama
    try {
        $ollama = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5 -ErrorAction Stop
        $models = ($ollama.models | ForEach-Object { $_.name }) -join ", "
        Write-Host "  [OK] Ollama is running (models: $models)" -ForegroundColor Green
    } catch {
        Write-Host "  [X] Ollama is not running - run 'ollama serve'" -ForegroundColor Red
    }
    
    Test-ServiceHealth "http://localhost:$VectorPort/health" "Vector Index (port $VectorPort)"
    Test-ServiceHealth "http://localhost:$ApiPort/health" "API Gateway (port $ApiPort)"
    
    Write-Host ""
    exit
}

# Stop all services
if ($StopAll) {
    Write-Host "Stopping all ContextForge services..." -ForegroundColor Yellow
    
    if ($Docker) {
        docker-compose down
    } else {
        # Find and kill Python processes on our ports
        $ports = @($ApiPort, $VectorPort, 8002, 8003, 8004, 8006)
        foreach ($port in $ports) {
            $pids = netstat -aon | findstr ":$port " | findstr "LISTENING" | ForEach-Object {
                ($_ -split '\s+')[-1]
            } | Sort-Object -Unique
            foreach ($processId in $pids) {
                if ($processId -match '^\d+$') {
                    Write-Host "  Killing process $processId on port $port" -ForegroundColor Yellow
                    taskkill /F /PID $processId 2>$null
                }
            }
        }
    }
    Write-Host "Done!" -ForegroundColor Green
    exit
}

# Docker mode
if ($Docker) {
    Write-Host "Starting ContextForge with Docker Compose..." -ForegroundColor Yellow
    Write-Host ""
    
    # Check Docker
    try {
        docker ps 2>&1 | Out-Null
    } catch {
        Write-Host "[ERROR] Docker is not running. Please start Docker Desktop." -ForegroundColor Red
        exit 1
    }
    
    # Check Ollama for Docker
    try {
        Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5 -ErrorAction Stop | Out-Null
        Write-Host "[OK] Ollama is running" -ForegroundColor Green
    } catch {
        Write-Host "[WARNING] Ollama is not running. Docker services will try to connect to host.docker.internal:11434" -ForegroundColor Yellow
        Write-Host "         Start Ollama with: ollama serve" -ForegroundColor Yellow
    }
    
    Set-Location $ProjectRoot
    docker-compose up -d --build
    
    Write-Host ""
    Write-Host "Services starting... waiting 10 seconds for health check" -ForegroundColor Yellow
    Start-Sleep -Seconds 10
    
    & $PSCommandPath -Status
    exit
}

# Local development mode
Write-Host "Starting ContextForge in local development mode..." -ForegroundColor Yellow
Write-Host ""

# Check prerequisites
Write-Host "Checking prerequisites..." -ForegroundColor Yellow

# Check Ollama
try {
    $ollama = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "  [OK] Ollama is running" -ForegroundColor Green
    if ($ollama.models.Count -eq 0) {
        Write-Host "  [WARNING] No models found. Run: ollama pull mistral" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  [X] Ollama is not running" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Please start Ollama first:" -ForegroundColor Yellow
    Write-Host "    1. Run 'ollama serve' in a separate terminal" -ForegroundColor White
    Write-Host "    2. Run 'ollama pull mistral' to download a model" -ForegroundColor White
    Write-Host ""
    exit 1
}

# Check virtual environment
if (-not (Test-Path "$ProjectRoot\venv\Scripts\activate.ps1")) {
    Write-Host "  [X] Virtual environment not found. Creating..." -ForegroundColor Yellow
    python -m venv "$ProjectRoot\venv"
    & "$ProjectRoot\venv\Scripts\activate.ps1"
    pip install --upgrade pip
    pip install -r "$ProjectRoot\requirements.txt"
}
Write-Host "  [OK] Virtual environment exists" -ForegroundColor Green

# Check for port conflicts
if (Test-Port $VectorPort) {
    Write-Host "  [WARNING] Port $VectorPort is already in use" -ForegroundColor Yellow
}
if (Test-Port $ApiPort) {
    Write-Host "  [WARNING] Port $ApiPort is already in use" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Starting services..." -ForegroundColor Yellow
Write-Host ""

# Start Vector Index in background
Write-Host "  Starting Vector Index on port $VectorPort..." -ForegroundColor White
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$ProjectRoot'; .\venv\Scripts\activate; `$env:PYTHONPATH = 'services\vector_index;.'; python -m uvicorn services.vector_index.app:app --host 0.0.0.0 --port $VectorPort"
)

Start-Sleep -Seconds 3

# Start API Gateway in background
Write-Host "  Starting API Gateway on port $ApiPort..." -ForegroundColor White
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$ProjectRoot'; .\venv\Scripts\activate; `$env:PYTHONPATH = 'services\api_gateway;.'; python -m uvicorn services.api_gateway.app:app --host 0.0.0.0 --port $ApiPort"
)

Write-Host ""
Write-Host "Waiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Health check
Write-Host ""
Write-Host "Checking service health..." -ForegroundColor Yellow
& $PSCommandPath -Status -ApiPort $ApiPort -VectorPort $VectorPort

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "   ContextForge is ready!" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "API Gateway: http://localhost:$ApiPort" -ForegroundColor White
Write-Host "Health Check: http://localhost:$ApiPort/health" -ForegroundColor White
Write-Host ""
Write-Host "Test with:" -ForegroundColor Yellow
Write-Host "  curl http://localhost:$ApiPort/health" -ForegroundColor White
Write-Host ""
Write-Host "VS Code: Set 'Contextforge: Api Url' to http://localhost:$ApiPort" -ForegroundColor Yellow
Write-Host ""
Write-Host "To stop all services: .\start-contextforge.ps1 -StopAll" -ForegroundColor Yellow

