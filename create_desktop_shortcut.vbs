' ==============================================================================
' Tamil MP3 Downloader — Create Desktop Shortcut
' ==============================================================================
' Creates a desktop shortcut configured to run silently with wscript.exe
' ==============================================================================

Option Explicit

Dim shell, fso, desktopPath, shortcutPath, shortcut, appDir, vbsPath, iconPath

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

appDir = fso.GetParentFolderName(WScript.ScriptFullName)
vbsPath = appDir & "\launch_app.vbs"
desktopPath = shell.SpecialFolders("Desktop")
shortcutPath = desktopPath & "\Tamil MP3 Downloader.lnk"

Set shortcut = shell.CreateShortcut(shortcutPath)
shortcut.TargetPath = "wscript.exe"
shortcut.Arguments = """" & vbsPath & """"
shortcut.WorkingDirectory = appDir
shortcut.Description = "Tamil MP3 Downloader — High Fidelity Music Library"

iconPath = appDir & "\assets\icon.ico"
If fso.FileExists(iconPath) Then
    shortcut.IconLocation = iconPath
Else
    shortcut.IconLocation = "shell32.dll,220"
End If

shortcut.Save

If WScript.Interactive Then
    WScript.Echo "Desktop shortcut created successfully at: " & shortcutPath
End If
