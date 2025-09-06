Option Explicit

Const URL1 = "http://127.0.0.1:5000/"
Const URL2 = "http://localhost:5000/"
Const TIMEOUT = 30000
Const WIN_W = 1280
Const WIN_H = 800

Dim fso, sh, appDir, cmd, url
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh  = CreateObject("WScript.Shell")

appDir = fso.GetParentFolderName(WScript.ScriptFullName)

If Not fso.FileExists(appDir & "\python\python.exe") Then
  MsgBox "Introuvable: " & appDir & "\python\python.exe", 16, "Erreur"
  WScript.Quit 1
End If
If Not fso.FileExists(appDir & "\admin.py") Then
  MsgBox "Introuvable: " & appDir & "\admin.py", 16, "Erreur"
  WScript.Quit 1
End If

cmd = "cmd.exe /c cd /d " & QQ(appDir) & " && " & QQ("python\python.exe") & " " & QQ("admin.py")
sh.Run cmd, 0, False

If WaitUrl(URL1, TIMEOUT) Then
  url = URL1
ElseIf WaitUrl(URL2, 6000) Then
  url = URL2
Else
  MsgBox "Serveur non joignable.", 16, "Erreur"
  WScript.Quit 3
End If

If OpenChromiumApp(EdgePath(), url, WIN_W, WIN_H) Then WScript.Quit 0
If OpenChromiumApp(ChromePath(), url, WIN_W, WIN_H) Then WScript.Quit 0
If OpenChromiumApp(BravePath(), url, WIN_W, WIN_H) Then WScript.Quit 0
If OpenChromiumApp(VivaldiPath(), url, WIN_W, WIN_H) Then WScript.Quit 0
If OpenChromiumApp(OperaPath(), url, WIN_W, WIN_H) Then WScript.Quit 0
If OpenFirefoxWindow(FirefoxPath(), url) Then WScript.Quit 0

sh.Run url, 1, False
WScript.Quit 0

Function QQ(s) : QQ = """" & s & """" : End Function

Function WaitUrl(u, ms)
  Dim t0: t0 = Timer
  WaitUrl = False
  Do While ((Timer - t0) * 1000) < ms
    If UrlOK(u) Then WaitUrl = True : Exit Function
    WScript.Sleep 250
  Loop
End Function

Function UrlOK(u)
  On Error Resume Next
  Dim x: Set x = CreateObject("MSXML2.XMLHTTP")
  x.Open "GET", u, False
  x.Send
  UrlOK = (x.readyState = 4 And x.Status >= 200 And x.Status < 400)
  Set x = Nothing
  On Error GoTo 0
End Function

Function EdgePath()
  Dim p
  p = sh.ExpandEnvironmentStrings("%ProgramFiles(x86)%") & "\Microsoft\Edge\Application\msedge.exe"
  If fso.FileExists(p) Then EdgePath = p : Exit Function
  p = sh.ExpandEnvironmentStrings("%ProgramFiles%") & "\Microsoft\Edge\Application\msedge.exe"
  If fso.FileExists(p) Then EdgePath = p Else EdgePath = ""
End Function

Function ChromePath()
  Dim p
  p = sh.ExpandEnvironmentStrings("%ProgramFiles%") & "\Google\Chrome\Application\chrome.exe"
  If fso.FileExists(p) Then ChromePath = p : Exit Function
  p = sh.ExpandEnvironmentStrings("%ProgramFiles(x86)%") & "\Google\Chrome\Application\chrome.exe"
  If fso.FileExists(p) Then ChromePath = p Else ChromePath = ""
End Function

Function BravePath()
  Dim p
  p = sh.ExpandEnvironmentStrings("%ProgramFiles%") & "\BraveSoftware\Brave-Browser\Application\brave.exe"
  If fso.FileExists(p) Then BravePath = p : Exit Function
  p = sh.ExpandEnvironmentStrings("%ProgramFiles(x86)%") & "\BraveSoftware\Brave-Browser\Application\brave.exe"
  If fso.FileExists(p) Then BravePath = p Else BravePath = ""
End Function

Function VivaldiPath()
  Dim p
  p = sh.ExpandEnvironmentStrings("%ProgramFiles%") & "\Vivaldi\Application\vivaldi.exe"
  If fso.FileExists(p) Then VivaldiPath = p : Exit Function
  p = sh.ExpandEnvironmentStrings("%ProgramFiles(x86)%") & "\Vivaldi\Application\vivaldi.exe"
  If fso.FileExists(p) Then VivaldiPath = p Else VivaldiPath = ""
End Function

Function OperaPath()
  Dim p
  p = sh.ExpandEnvironmentStrings("%ProgramFiles%") & "\Opera\opera.exe"
  If fso.FileExists(p) Then OperaPath = p : Exit Function
  p = sh.ExpandEnvironmentStrings("%ProgramFiles(x86)%") & "\Opera\opera.exe"
  If fso.FileExists(p) Then OperaPath = p Else OperaPath = ""
End Function

Function FirefoxPath()
  Dim p
  p = sh.ExpandEnvironmentStrings("%ProgramFiles%") & "\Mozilla Firefox\firefox.exe"
  If fso.FileExists(p) Then FirefoxPath = p : Exit Function
  p = sh.ExpandEnvironmentStrings("%ProgramFiles(x86)%") & "\Mozilla Firefox\firefox.exe"
  If fso.FileExists(p) Then FirefoxPath = p Else FirefoxPath = ""
End Function

Function OpenChromiumApp(exe, u, w, h)
  OpenChromiumApp = False
  If Len(exe)=0 Then Exit Function
  Dim args
  args = " --new-window --window-size=" & CStr(w) & "," & CStr(h) & " --app=" & QQ(u)
  sh.Run QQ(exe) & args, 1, False
  OpenChromiumApp = True
End Function

Function OpenFirefoxWindow(exe, u)
  OpenFirefoxWindow = False
  If Len(exe)=0 Then Exit Function
  sh.Run QQ(exe) & " -private-window " & QQ(u), 1, False
  OpenFirefoxWindow = True
End Function
