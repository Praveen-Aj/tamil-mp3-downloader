' ==============================================================================
' Tamil MP3 Downloader — Silent Desktop Launcher
' ==============================================================================
' Runs FastAPI silently using pythonw.exe without any command prompt window.
' Provides duplicate instance protection, automatic browser launch, and error alerts.
' ==============================================================================

Option Explicit

Dim fso, shell, appDir, pythonwExe, url, healthUrl, runServerPy
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

appDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonwExe = appDir & "\.venv\Scripts\pythonw.exe"
runServerPy = appDir & "\run_server.py"
url = "http://127.0.0.1:8765"
healthUrl = "http://127.0.0.1:8765/api/system/health"

If Not fso.FileExists(pythonwExe) Then
    MsgBox "Python virtual environment not found at:" & vbCrLf & pythonwExe & vbCrLf & vbCrLf & _
           "Please ensure the .venv folder is properly installed.", vbCritical, "Tamil MP3 Downloader"
    WScript.Quit 1
End If

' Function to check if server is reachable and healthy
Function IsServerRunning()
    IsServerRunning = False
    On Error Resume Next
    Dim http
    Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    If http Is Nothing Then Set http = CreateObject("MSXML2.ServerXMLHTTP")
    http.open "GET", healthUrl, False
    http.setTimeouts 500, 500, 500, 500
    http.send
    If Err.Number = 0 Then
        If http.status = 200 Or http.status = 304 Then
            IsServerRunning = True
        End If
    End If
    Set http = Nothing
    On Error GoTo 0
End Function

' 1. Duplicate instance check: If already running, simply open browser and exit
If IsServerRunning() Then
    shell.Run url, 1, False
    WScript.Quit 0
End If

' 2. Launch FastAPI silently using pythonw.exe (Window style 0 = Hidden)
shell.CurrentDirectory = appDir
Dim runCmd
runCmd = """" & pythonwExe & """ """ & runServerPy & """"
shell.Run runCmd, 0, False

' 3. Wait up to 15 seconds for server to become healthy
Dim attempts, maxAttempts, isReady
attempts = 0
maxAttempts = 30
isReady = False

Do While attempts < maxAttempts
    WScript.Sleep 500
    If IsServerRunning() Then
        isReady = True
        Exit Do
    End If
    attempts = attempts + 1
Loop

' 4. Open default browser on success or display user-friendly alert on failure
If isReady Then
    shell.Run url, 1, False
Else
    MsgBox "Tamil MP3 Downloader could not start within 15 seconds." & vbCrLf & vbCrLf & _
           "Please check whether port 8765 is occupied by another application or inspect backend logs.", _
           vbCritical, "Tamil MP3 Downloader Startup"
    WScript.Quit 1
End If
