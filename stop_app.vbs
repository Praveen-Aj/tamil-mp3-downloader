' ==============================================================================
' Tamil MP3 Downloader — Stop Server
' ==============================================================================
' Cleanly and silently terminates the local server process running on port 8765.
' ==============================================================================

Option Explicit

Dim shell, returnCode, psCmd
Set shell = CreateObject("WScript.Shell")

psCmd = "powershell.exe -NoProfile -WindowStyle Hidden -Command """ & _
        "$conns = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue; " & _
        "if ($conns) { foreach ($c in $conns) { Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue }; exit 0 } else { exit 2 }"""

returnCode = shell.Run(psCmd, 0, True)

If returnCode = 0 Then
    MsgBox "Tamil MP3 Downloader server has been stopped.", vbInformation, "Tamil MP3 Downloader"
Else
    MsgBox "Tamil MP3 Downloader server is not currently running.", vbInformation, "Tamil MP3 Downloader"
End If
