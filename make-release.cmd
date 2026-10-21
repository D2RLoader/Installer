@echo off
rem Makes the website files of a release in out\release: manifest.json and each file of the release.
rem Drag the release zip (D2RLoader-<version>.zip) onto this file. Or run it in a terminal:
rem   make-release.cmd path\to\D2RLoader-1.4.0.zip
rem To make the files for a test folder on the website, give the web address of that folder as the second value:
rem   make-release.cmd path\to\D2RLoader-1.4.0.zip https://example.org/test/
rem Then upload the files in out\release, and upload manifest.json last.
setlocal

if "%~1"=="" (
	echo Drag the release zip onto this file, or run: make-release.cmd path\to\D2RLoader-1.4.0.zip
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

if exist out\release (
	echo Removing the old out\release folder.
	rmdir /s /q out\release
)
if "%~2"=="" (
	%PY% -I tools\make-manifest.py "%ZIP%" out\release
) else (
	%PY% -I tools\make-manifest.py "%ZIP%" out\release --base-url "%~2"
)
set "CODE=%ERRORLEVEL%"
if "%CODE%"=="0" if not defined D2RL_NO_PAUSE start "" explorer out\release

:done
echo.
if "%CODE%"=="0" (echo Done.) else (echo FAILED. Read the messages above.)
if not defined D2RL_NO_PAUSE pause
exit /b %CODE%
