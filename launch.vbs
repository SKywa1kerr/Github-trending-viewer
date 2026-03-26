Set WshShell = CreateObject("WScript.Shell")

' 检查 Docker 容器是否运行
Set exec = WshShell.Exec("docker ps --filter name=github-trending --format ""{{.Names}}""")
output = exec.StdOut.ReadAll()

If InStr(output, "github-trending") = 0 Then
    ' 启动容器
    WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
    WshShell.Run "docker-compose up -d", 0, True
    ' 等待服务就绪
    WScript.Sleep 5000
    Dim attempts
    attempts = 0
    Do While attempts < 30
        On Error Resume Next
        Set http = CreateObject("MSXML2.XMLHTTP")
        http.Open "GET", "http://localhost:8088/api/status", False
        http.Send
        If http.Status = 200 Then Exit Do
        On Error GoTo 0
        WScript.Sleep 2000
        attempts = attempts + 1
    Loop
End If

' 尝试用 Edge --app 模式打开
WshShell.Run "msedge --app=http://localhost:8088 --window-size=1200,800", 1, False
