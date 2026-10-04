@echo off
rem Builds NovaScript-<version>.zip for a GitHub release: everything users need
rem (NovaScript.exe included), none of the app source (desktop), build output or local data.
rem Attach the zip as the FIRST file on the release - the updater downloads that one.
setlocal
cd /d "%~dp0"

for /f "usebackq delims=" %%v in (`powershell -NoProfile -Command "(Get-Content 'novascript-extension\manifest.json' -Raw | ConvertFrom-Json).version"`) do set "VER=%%v"
if not defined VER (
  echo Could not read the version from novascript-extension\manifest.json
  pause
  exit /b 1
)

if not exist "NovaScript.exe" (
  echo NovaScript.exe is missing. Build it first: cd desktop, npm run build -- --no-bundle,
  echo then copy desktop\src-tauri\target\release\novascript.exe here as NovaScript.exe.
  pause
  exit /b 1
)

set "STAGE=%TEMP%\vs_release\NovaScript"
set "OUT=%~dp0NovaScript-%VER%.zip"
if exist "%TEMP%\vs_release" rmdir /s /q "%TEMP%\vs_release"
if exist "%OUT%" del /q "%OUT%"

echo Packing NovaScript %VER%...
robocopy "%~dp0." "%STAGE%" /E /NFL /NDL /NJH /NJS /NP ^
  /XD .git .kilo desktop target node_modules gen logs backups __pycache__ ^
  /XF check_update.json *.old *.zip *.pyc make-release.bat >nul
if errorlevel 8 (
  echo Copy failed.
  pause
  exit /b 1
)

powershell -NoProfile -Command "Compress-Archive -Path '%STAGE%' -DestinationPath '%OUT%' -Force"
rmdir /s /q "%TEMP%\vs_release"
if not exist "%OUT%" (
  echo Zipping failed.
  pause
  exit /b 1
)

echo.
echo Done: NovaScript-%VER%.zip
echo Upload it as the first file on the V%VER% GitHub release.
pause
