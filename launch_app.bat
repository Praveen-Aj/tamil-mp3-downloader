@echo off
setlocal

set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

set "PYTHON=%APP_DIR%.venv\Scripts\python.exe"
set "URL=http://127.0.0.1:8765"

REM Check whether the web server is already running
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%URL%' -UseBasicParsing -TimeoutSec 1 | Out-Null; exit 0 } catch { exit 1 }"

if %errorlevel%==0 (
    start "" "%URL%"
    exit /b 0
)

REM Start FastAPI web application
start "Tamil MP3 Downloader Server" /min "%PYTHON%" -m uvicorn api.app:app --host 127.0.0.1 --port 8765

REM Wait for the server to become available
:wait
timeout /t 1 /nobreak >nul

powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%URL%' -UseBasicParsing -TimeoutSec 1 | Out-Null; exit 0 } catch { exit 1 }"

if not %errorlevel%==0 goto wait

REM Open the web application
start "" "%URL%"

exit /b 0