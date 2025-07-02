@echo off
REM 
set "SCRIPT_DIR=%~dp0"

REM 
set "VBS_PATH=%SCRIPT_DIR%SRC\lancer_xvlm_silence.vbs"
set "ICON_PATH=%SCRIPT_DIR%SRC\xvlm.ico"

REM 
set "SHORTCUT_PATH=%USERPROFILE%\Desktop\XVLIVEMANAGER.lnk"

REM 
powershell -NoProfile -Command ^
  "$W = New-Object -ComObject WScript.Shell; " ^
  "$L = $W.CreateShortcut('%SHORTCUT_PATH%'); " ^
  "$L.TargetPath = '%VBS_PATH%'; " ^
  "$L.IconLocation = '%ICON_PATH%'; " ^
  "$L.WorkingDirectory = '%SCRIPT_DIR%'; " ^
  "$L.Save()"
