@echo off
setlocal

REM Makes the postcards. Double-click this file, or type run in a terminal.
REM
REM Windows cannot currently find Python by name, so this falls back to the
REM copy that is actually installed on this machine. If you later install
REM Python properly and tick "Add python.exe to PATH", this will pick that
REM one up instead and carry on working.

set "PYEXE=C:\ProgramData\miniforge3\python.exe"
where python >nul 2>nul && set "PYEXE=python"

echo Using: %PYEXE%
echo.

"%PYEXE%" "%~dp0make_postcards.py" "%~dp0walks"

echo.
pause
