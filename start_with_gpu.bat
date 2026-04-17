@echo off
REM Start Fed-Med-FL with GPU Support
REM Prerequisites:
REM   1. NVIDIA GPU with CUDA support
REM   2. NVIDIA Docker runtime installed
REM   3. Docker Desktop with WSL2 backend

echo ==========================================
echo Fed-Med-FL - GPU Mode
echo ==========================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running!
    echo Please start Docker Desktop first.
    pause
    exit /b 1
)

echo Checking NVIDIA GPU support...
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi >nul 2>&1
if errorlevel 1 (
    echo.
    echo WARNING: NVIDIA GPU not detected or Docker GPU support not configured!
    echo.
    echo To enable GPU support:
    echo   1. Install NVIDIA Container Toolkit
    echo   2. Enable WSL2 integration in Docker Desktop
    echo   3. Restart Docker Desktop
    echo.
    echo Continuing with CPU mode...
    echo.
    set USE_GPU=no
) else (
    echo GPU detected! Starting with GPU support...
    set USE_GPU=yes
)

echo.
echo Stopping existing containers...
docker compose down

echo.
echo Building images...
if "%USE_GPU%"=="yes" (
    docker compose -f docker-compose.yml -f docker-compose.gpu.yml build
) else (
    docker compose build
)

echo.
echo Starting services...
if "%USE_GPU%"=="yes" (
    docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
) else (
    docker compose up -d
)

echo.
echo Waiting for services to start...
timeout /t 30 /nobreak >nul

echo.
echo ==========================================
echo Services Started!
echo ==========================================
echo.
echo Central Server: http://localhost:8080
echo Node1 UI:       http://localhost:3001
echo Node2 UI:       http://localhost:3002
echo Node3 UI:       http://localhost:3003
echo.
if "%USE_GPU%"=="yes" (
    echo GPU Mode: ENABLED
) else (
    echo GPU Mode: DISABLED (using CPU)
)
echo.
echo Press any key to view logs (Ctrl+C to exit)...
pause >nul

docker compose logs -f
