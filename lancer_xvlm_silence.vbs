Option Explicit
Dim fso, shell
Dim vbsFolder, installFolder
Dim pythonExe, adminScript

Set fso   = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

' 1) dossier où est ce .vbs
vbsFolder = fso.GetParentFolderName(WScript.ScriptFullName)
' si le VBS est à la racine, installFolder = vbsFolder, sinon si dans SRC, parent
If LCase(fso.GetFileName(vbsFolder)) = "src" Then
  installFolder = fso.GetParentFolderName(vbsFolder)
Else
  installFolder = vbsFolder
End If

' 2) cherche python.exe
If fso.FileExists(installFolder & "\python\python.exe") Then
  pythonExe = installFolder & "\python\python.exe"
ElseIf fso.FileExists(installFolder & "\SRC\python\python.exe") Then
  pythonExe = installFolder & "\SRC\python\python.exe"
Else
  MsgBox "python.exe introuvable dans : " & vbCrLf & _
         installFolder & "\python\python.exe" & vbCrLf & _
         "ni dans : " & installFolder & "\SRC\python\python.exe", 16, "Erreur"
  WScript.Quit
End If

' 3) cherche admin.py
If fso.FileExists(installFolder & "\admin.py") Then
  adminScript = installFolder & "\admin.py"
ElseIf fso.FileExists(installFolder & "\SRC\admin.py") Then
  adminScript = installFolder & "\SRC\admin.py"
Else
  MsgBox "admin.py introuvable dans : " & vbCrLf & _
         installFolder & "\admin.py" & vbCrLf & _
         "ni dans : " & installFolder & "\SRC\admin.py", 16, "Erreur"
  WScript.Quit
End If

' 4) lance
shell.CurrentDirectory = installFolder
shell.Run """" & pythonExe & """" & " " & """" & adminScript & """", 0, False

WScript.Sleep 3000
shell.Run "explorer.exe http://localhost:5000/", 1, False
