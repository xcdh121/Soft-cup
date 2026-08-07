@echo off
setlocal
title Wanjing Local Launcher

rem Always run from the folder containing this script.
cd /d "%~dp0"

set "WEB_DIR=%CD%\src\edu-web"

echo ========================================
echo       Wanjing Local Launcher
echo ========================================
echo.

where docker >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker was not found.
    echo Install and start Docker Desktop, then run this script again.
    goto :failed
)

docker compose version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] The "docker compose" command is unavailable.
    echo Install or update Docker Desktop.
    goto :failed
)

docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Desktop is not running or is not ready.
    echo Start Docker Desktop and wait for initialization to finish.
    goto :failed
)

if not exist ".env" (
    echo [ERROR] The .env file is missing from the project root.
    echo Create .env from .env.example and fill in the required settings.
    goto :failed
)

if not exist "docker-compose.yaml" (
    echo [ERROR] docker-compose.yaml was not found.
    echo Put this script in the project root next to docker-compose.yaml.
    goto :failed
)

where npm >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm was not found.
    echo The frontend is not yet in Docker Compose. Install Node.js 20 or newer.
    goto :failed
)

if not exist "%WEB_DIR%\package.json" (
    echo [ERROR] Frontend project not found: %WEB_DIR%\package.json
    echo Check that the src\edu-web directory is complete.
    goto :failed
)

echo [1/3] Building and starting backend services...
docker compose up -d --build
if errorlevel 1 (
    echo.
    echo [ERROR] Docker services failed to start. Review the output above.
    goto :failed
)

echo.
echo [2/3] Checking frontend dependencies...
pushd "%WEB_DIR%"
if not exist "node_modules" (
    echo Installing frontend dependencies for the first run...
    call npm ci
    if errorlevel 1 (
        popd
        echo.
        echo [ERROR] Frontend dependency installation failed.
        echo Check the network connection and npm configuration.
        goto :failed
    )
)

echo.
echo [3/3] Starting the frontend development server...
start "Wanjing Frontend" cmd /k "npm start"
popd

echo.
echo ========================================
echo Wanjing startup commands completed.
echo.
echo Local frontend: http://localhost:3000
echo Backend API:    http://localhost:8000
echo.
echo The frontend runs in the newly opened command window.
echo Closing that window stops the frontend only.
echo Docker backend services continue running in the background.
echo ========================================
echo.
pause
exit /b 0

:failed
echo.
echo Wanjing startup did not complete.
pause
exit /b 1
