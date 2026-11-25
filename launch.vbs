' Double-click: start the app and open it. With the "background" argument (used by the
' Windows startup shortcut): start it silently so the bookmark http://127.0.0.1:8098 just works.
Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")

projectDir = fso.GetParentFolderName(WScript.ScriptFullName)
scriptPath = fso.BuildPath(projectDir, "start-local.ps1")
command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File " & Chr(34) & scriptPath & Chr(34)
If WScript.Arguments.Count > 0 Then
    If LCase(WScript.Arguments(0)) = "background" Then command = command & " -NoOpen"
End If
WshShell.Run command, 0, False
