@echo off
REM ==============================================================================
REM Tamil MP3 Downloader — Stop Batch Helper
REM Delegates to silent VBScript stop helper via wscript.exe
REM ==============================================================================
set "APP_DIR=%~dp0"
start "" wscript.exe "%APP_DIR%stop_app.vbs"
exit /b 0
