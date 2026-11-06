@echo off
rem Hidden launcher: starts the tracker with no console window.
set "PYW=%~dp0runtime\python\pythonw.exe"
if exist "%PYW%" (
  start "" "%PYW%" "%~dp0run.py" %*
) else (
  echo Runtime missing. Run: python tools\setup.py
  pause
)
