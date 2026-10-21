@echo off
rem Uploads a release to the website over SSH. Drag the release zip (D2RLoader-<version>.zip) onto this file.
rem Or run it in a terminal:
rem   .\publish-release.cmd path\to\D2RLoader-1.4.0.zip
rem First time: copy publish.env.example to publish.env and fill it in.
rem The script asks where to publish (the test folder or the live site), shows what it will upload,
rem and asks you to type yes. It uploads manifest.json last, and then checks the public files.
setlocal

if "%~1"=="" (
	echo Drag the release zip onto this file, or run: publish-release.cmd path\to\D2RLoader-1.4.0.zip
	set "CODE=1"
	goto :done
)
set "ZIP=%~f1"
if not exist "%ZIP%" (
	echo The zip was not found: %ZIP%
	set "CODE=1"
	goto :done
)
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

%PY% -I tools\publish.py release "%ZIP%"
set "CODE=%ERRORLEVEL%"

:done
echo.
if "%CODE%"=="0" (echo Done.) else (echo FAILED. Read the messages above.)
if not defined D2RL_NO_PAUSE pause
exit /b %CODE%
