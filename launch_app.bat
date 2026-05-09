@echo off
REM Tamil MP3 Downloader Launcher - No console window
setlocal
set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"
start "" "%APP_DIR%.venv\Scripts\pythonw.exe" "%APP_DIR%main.py"
exit