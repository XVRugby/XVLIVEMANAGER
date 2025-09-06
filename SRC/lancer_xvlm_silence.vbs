Option Explicit
Dim fso, shell
Dim vbsFolder, installFolder
Dim pythonExe, pythonwExe, adminScript
Dim url, winW, winH, appUrl
Dim gPid : gPid = 0
Dim gPyPid : gPyPid = 0
Dim gProfileDir : gProfileDir = ""

Set fso   = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
Randomize

url  = "http://localhost:5000/"
winW = 1280
winH = 800

vbsFolder = fso.GetParentFolderName(WScript.ScriptFullName)
If LCase(fso.GetFileName(vbsFolder)) = "src" Then
  installFolder = fso.GetParentFolderName(vbsFolder)
Else
  installFolder = vbsFolder
End If

' --- Détection python.exe et pythonw.exe ---
If fso.FileExists(installFolder & "\python\pythonw.exe") Then
  pythonwExe = installFolder & "\python\pythonw.exe"
  pythonExe  = installFolder & "\python\python.exe"
ElseIf fso.FileExists(installFolder & "\SRC\python\pythonw.exe") Then
  pythonwExe = installFolder & "\SRC\python\pythonw.exe"
  pythonExe  = installFolder & "\SRC\python\python.exe"
ElseIf fso.FileExists(installFolder & "\python\python.exe") Then
  pythonExe  = installFolder & "\python\python.exe"
ElseIf fso.FileExists(installFolder & "\SRC\python\python.exe") Then
  pythonExe  = installFolder & "\SRC\python\python.exe"
Else
  WScript.Quit 1
End If

' --- Localisation admin.py ---
If fso.FileExists(installFolder & "\admin.py") Then
  adminScript = installFolder & "\admin.py"
ElseIf fso.FileExists(installFolder & "\SRC\admin.py") Then
  adminScript = installFolder & "\SRC\admin.py"
Else
  WScript.Quit 1
End If

shell.CurrentDirectory = installFolder

' --- Lancement Python sans console ---
If Len(pythonwExe) > 0 And fso.FileExists(pythonwExe) Then
  gPyPid = StartProcessGetPid(pythonwExe, Quote(adminScript))
Else
  gPyPid = StartProcessGetPid(pythonExe, Quote(adminScript))
End If
If gPyPid = 0 Then WScript.Quit 2

If Not WaitUrl(url, 15000) Then
  KillPid gPyPid
  WScript.Quit 3
End If

appUrl = url & "?ts=" & Hex(CLng(Timer()*1000))

Dim launched : launched = False
If Not launched Then If OpenEdgeApp(appUrl, winW, winH)    Then launched = True
If Not launched Then If OpenChromeApp(appUrl, winW, winH)  Then launched = True
If Not launched Then If OpenBraveApp(appUrl, winW, winH)   Then launched = True
If Not launched Then If OpenVivaldiApp(appUrl, winW, winH) Then launched = True
If Not launched Then If OpenOperaApp(appUrl, winW, winH)   Then launched = True
If Not launched Then If OpenFirefoxKiosk(appUrl)           Then launched = True

If Not launched Then
  shell.Run appUrl, 1, False
  WScript.Sleep 500
Else
  Do
    If gPid>0 And Not IsAlive(gPid) Then Exit Do
    If gPyPid>0 And Not IsAlive(gPyPid) Then Exit Do
    WScript.Sleep 300
  Loop
End If

KillBrowserInstance gPid, gProfileDir
KillPid gPyPid
If Len(gProfileDir)>0 Then On Error Resume Next: If CreateObject("Scripting.FileSystemObject").FolderExists(gProfileDir) Then CreateObject("Scripting.FileSystemObject").DeleteFolder gProfileDir, True: On Error GoTo 0
WScript.Quit 0

' ================== OUTILS ==================
Function Quote(s) : Quote = """" & s & """" : End Function

Function StartProcessGetPid(exe, args)
  On Error Resume Next
  Dim svc, proc, rc, pid
  Set svc  = GetObject("winmgmts:\\.\root\cimv2")
  Set proc = svc.Get("Win32_Process")
  rc = proc.Create(Quote(exe) & " " & args, Null, Null, pid)
  If rc = 0 Then StartProcessGetPid = pid Else StartProcessGetPid = 0
  On Error GoTo 0
End Function

Function IsAlive(pid)
  On Error Resume Next
  Dim svc, col
  Set svc = GetObject("winmgmts:\\.\root\cimv2")
  Set col = svc.ExecQuery("SELECT * FROM Win32_Process WHERE ProcessId=" & pid)
  IsAlive = (col.Count > 0)
  On Error GoTo 0
End Function

Sub KillPid(pid)
  On Error Resume Next
  If pid > 0 Then
    Dim svc, col, itm
    Set svc = GetObject("winmgmts:\\.\root\cimv2")
    Set col = svc.ExecQuery("SELECT * FROM Win32_Process WHERE ProcessId=" & pid)
    For Each itm In col : itm.Terminate : Next
  End If
  On Error GoTo 0
End Sub

Function MakeProfileDir()
  Dim p, t
  t = CreateObject("WScript.Shell").ExpandEnvironmentStrings("%TEMP%")
  p = t & "\XVLIVEAPP-" & Hex(CLng(Timer()*1000)) & "-" & CStr(Int(Rnd()*1000000))
  On Error Resume Next
  CreateObject("Scripting.FileSystemObject").CreateFolder p
  On Error GoTo 0
  MakeProfileDir = p
End Function

Sub KillBrowserInstance(pid, profileDir)
  On Error Resume Next
  KillPid pid
  WScript.Sleep 150
  If Len(profileDir) > 0 Then
    Dim svc, col, itm, q
    Set svc = GetObject("winmgmts:\\.\root\cimv2")
    q = "SELECT * FROM Win32_Process WHERE CommandLine LIKE ""%" & Replace(profileDir, """", """""") & "%"""
    Set col = svc.ExecQuery(q)
    For Each itm In col : itm.Terminate : Next
  End If
  On Error GoTo 0
End Sub

Function ChromiumArgs(u, w, h)
  gProfileDir = MakeProfileDir()
  ChromiumArgs = "--user-data-dir=" & Quote(gProfileDir) & _
                 " --disable-extensions --no-first-run --no-default-browser-check" & _
                 " --new-window --window-size=" & CStr(w) & "," & CStr(h) & _
                 " --app=" & Quote(u)
End Function

Function OpenEdgeApp(u, w, h)
  Dim exe, args, pid
  OpenEdgeApp = False
  exe = CreateObject("WScript.Shell").ExpandEnvironmentStrings("%ProgramFiles(x86)%") & "\Microsoft\Edge\Application\msedge.exe"
  If Not CreateObject("Scripting.FileSystemObject").FileExists(exe) Then exe = CreateObject("WScript.Shell").ExpandEnvironmentStrings("%ProgramFiles%") & "\Microsoft\Edge\Application\msedge.exe"
  If CreateObject("Scripting.FileSystemObject").FileExists(exe) Then
    args = ChromiumArgs(u, w, h)
    pid = StartProcessGetPid(exe, args)
    If pid > 0 Then gPid = pid: OpenEdgeApp = True
  End If
End Function

Function OpenChromeApp(u, w, h)
  Dim exe, args, pid
  OpenChromeApp = False
  exe = CreateObject("WScript.Shell").ExpandEnvironmentStrings("%ProgramFiles%") & "\Google\Chrome\Application\chrome.exe"
  If Not CreateObject("Scripting.FileSystemObject").FileExists(exe) Then exe = CreateObject("WScript.Shell").ExpandEnvironmentStrings("%ProgramFiles(x86)%") & "\Google\Chrome\Application\chrome.exe"
  If CreateObject("Scripting.FileSystemObject").FileExists(exe) Then
    args = ChromiumArgs(u, w, h)
    pid = StartProcessGetPid(exe, args)
    If pid > 0 Then gPid = pid: OpenChromeApp = True
  End If
End Function

Function OpenBraveApp(u, w, h)
  Dim exe, args, pid
  OpenBraveApp = False
  exe = CreateObject("WScript.Shell").ExpandEnvironmentStrings("%ProgramFiles%") & "\BraveSoftware\Brave-Browser\Application\brave.exe"
  If Not CreateObject("Scripting.FileSystemObject").FileExists(exe) Then exe = CreateObject("WScript.Shell").ExpandEnvironmentStrings("%ProgramFiles(x86)%") & "\BraveSoftware\Brave-Browser\Application\brave.exe"
  If CreateObject("Scripting.FileSystemObject").FileExists(exe) Then
    args = ChromiumArgs(u, w, h)
    pid = StartProcessGetPid(exe, args)
    If pid > 0 Then gPid = pid: OpenBraveApp = True
  End If
End Function

Function OpenVivaldiApp(u, w, h)
  Dim exe, args, pid
  OpenVivaldiApp = False
  exe = CreateObject("WScript.Shell").ExpandEnvironmentStrings("%ProgramFiles%") & "\Vivaldi\Application\vivaldi.exe"
  If Not CreateObject("Scripting.FileSystemObject").FileExists(exe) Then exe = CreateObject("WScript.Shell").ExpandEnvironmentStrings("%ProgramFiles(x86)%") & "\Vivaldi\Application\vivaldi.exe"
  If CreateObject("Scripting.FileSystemObject").FileExists(exe) Then
    args = ChromiumArgs(u, w, h)
    pid = StartProcessGetPid(exe, args)
    If pid > 0 Then gPid = pid: OpenVivaldiApp = True
  End If
End Function

Function OpenOperaApp(u, w, h)
  Dim exe, args, pid
  OpenOperaApp = False
  exe = CreateObject("WScript.Shell").ExpandEnvironmentStrings("%ProgramFiles%") & "\Opera\opera.exe"
  If Not CreateObject("Scripting.FileSystemObject").FileExists(exe) Then exe = CreateObject("WScript.Shell").ExpandEnvironmentStrings("%ProgramFiles(x86)%") & "\Opera\opera.exe"
  If CreateObject("Scripting.FileSystemObject").FileExists(exe) Then
    args = ChromiumArgs(u, w, h)
    pid = StartProcessGetPid(exe, args)
    If pid > 0 Then gPid = pid: OpenOperaApp = True
  End If
End Function

Function OpenFirefoxKiosk(u)
  Dim exe, args, pid
  OpenFirefoxKiosk = False
  gProfileDir = MakeProfileDir()
  exe = CreateObject("WScript.Shell").ExpandEnvironmentStrings("%ProgramFiles%") & "\Mozilla Firefox\firefox.exe"
  If Not CreateObject("Scripting.FileSystemObject").FileExists(exe) Then exe = CreateObject("WScript.Shell").ExpandEnvironmentStrings("%ProgramFiles(x86)%") & "\Mozilla Firefox\firefox.exe"
  If CreateObject("Scripting.FileSystemObject").FileExists(exe) Then
    args = "-no-remote -profile " & Quote(gProfileDir) & " --kiosk -private-window " & Quote(u)
    pid = StartProcessGetPid(exe, args)
    If pid > 0 Then gPid = pid: OpenFirefoxKiosk = True
  End If
End Function

Function WaitUrl(u, timeoutMs)
  Dim t0 : t0 = Timer()
  WaitUrl = False
  Do While ((Timer() - t0) * 1000) < timeoutMs
    If UrlOk(u) Then WaitUrl = True: Exit Function
    WScript.Sleep 250
  Loop
End Function

Function UrlOk(u)
  On Error Resume Next
  Dim xhr : Set xhr = CreateObject("MSXML2.XMLHTTP")
  xhr.Open "GET", u & "?_=" & CStr(Int(Rnd()*1000000)), False
  xhr.setRequestHeader "Cache-Control", "no-cache, no-store, must-revalidate"
  xhr.send
  UrlOk = (xhr.readyState = 4 And xhr.Status >= 200 And xhr.Status < 400)
  Set xhr = Nothing
  On Error GoTo 0
End Function

