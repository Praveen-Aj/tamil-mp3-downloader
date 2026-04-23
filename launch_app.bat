@echo off
REM Tamil MP3 Downloader Launcher - No console window
setlocal enabledelayedexpansion
cd /d "C:\Users\Praveen\Downloads\Python Scripts\tamil-mp3-downloader"
REM Use pythonw.exe to run without console window
start "" ".venv\Scripts\pythonw.exe" "main.py"
exit
