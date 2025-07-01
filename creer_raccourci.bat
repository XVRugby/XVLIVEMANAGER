@echo off
REM -- Répertoire où se trouve ce .bat (terminé par \)
set "SCRIPT_DIR=%~dp0"

REM -- Chemin complet vers votre VBS et votre icône
set "VBS_PATH=%SCRIPT_DIR%SRC\lancer_xvlm_silence.vbs"
set "ICON_PATH=%SCRIPT_DIR%SRC\xvlm.ico"

REM -- Emplacement du raccourci sur le Bureau
set "SHORTCUT_PATH=%USERPROFILE%\Desktop\XVLIVEMANAGER.lnk"

REM -- Création du raccourci via PowerShell
powershell -NoProfile -Command ^
  "$W = New-Object -ComObject WScript.Shell; " ^
  "$L = $W.CreateShortcut('%SHORTCUT_PATH%'); " ^
  "$L.TargetPath = '%VBS_PATH%'; " ^
  "$L.IconLocation = '%ICON_PATH%'; " ^
  "$L.WorkingDirectory = '%SCRIPT_DIR%'; " ^
  "$L.Save()"