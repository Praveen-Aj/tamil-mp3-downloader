REM Create launcher with hidden batch file
Set objShell = CreateObject("WScript.Shell")
Set objEnv = objShell.Environment("PROCESS")

strPath = "C:\Users\Praveen\Downloads\Python Scripts\tamil-mp3-downloader"
strPython = strPath & "\.venv\Scripts\python.exe"
strScript = strPath & "\main.py"

REM Change to app directory and run Python directly
objShell.CurrentDirectory = strPath
REM Run python directly without showing cmd window initially
objShell.Run """" & strPython & """ """ & strScript & """", 1, False
