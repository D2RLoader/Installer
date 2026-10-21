@echo off
rem Builds and runs every test of the installer. It takes a few minutes and needs Inno Setup 7.
rem Double-click this file, or run it in a terminal.
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

%PY% -I tests\run-all.py
set "CODE=%ERRORLEVEL%"

:done
echo.
if "%CODE%"=="0" (echo Done.) else (echo FAILED. Read the messages above.)
if not defined D2RL_NO_PAUSE pause
exit /b %CODE%
