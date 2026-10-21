@echo off
rem Builds the installer: out\D2RLoader-Installer.exe
rem Double-click this file, or run it in a terminal. You do not need to give any option.
rem It signs the installer when the D2RLoader certificate is in the Windows certificate store.
rem To build a test installer that reads another manifest, give the address of that manifest:
rem   build-installer.cmd https://example.org/test/manifest.json
rem The test installer is out\D2RLoader-Installer-staging.exe. It never replaces the real installer.
setlocal
cd /d "%~dp0"

set "PY="
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
	where python >nul 2>nul
	if not errorlevel 1 set "PY=python"
)
if not defined PY (
	echo Python 3 was not found. Install it from https://www.python.org/downloads/ and run this file again.
	set "CODE=1"
	goto :done
)

if "%~1"=="" (
	%PY% -I tools\build.py
) else (
	%PY% -I tools\build.py --manifest-url "%~1"
)
set "CODE=%ERRORLEVEL%"

:done
echo.
if "%CODE%"=="0" (echo Done.) else (echo FAILED. Read the messages above.)
if not defined D2RL_NO_PAUSE pause
exit /b %CODE%
