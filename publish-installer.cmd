@echo off
rem Uploads the installer (out\D2RLoader-Installer.exe) to the live folder of the website over SSH.
rem Build it first with build-installer.cmd. Use this only when the installer code changed.
rem First time: copy publish.env.example to publish.env and fill it in.
rem The script shows the file, its signature, and where it goes, and asks you to type yes.
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

%PY% -I tools\publish.py installer
set "CODE=%ERRORLEVEL%"

:done
echo.
if "%CODE%"=="0" (echo Done.) else (echo FAILED. Read the messages above.)
if not defined D2RL_NO_PAUSE pause
exit /b %CODE%
