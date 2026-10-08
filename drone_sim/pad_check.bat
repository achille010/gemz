@echo off
rem Opens the launcher straight on the controller check (pads / Bluetooth / orientation wizard).
cd /d "%~dp0"
set "PY=python"
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
%PY% launcher.py --pads
if errorlevel 1 pause
