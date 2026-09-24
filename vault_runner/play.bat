@echo off
cd /d "%~dp0"
rem Use the Windows "py" launcher when present (a plain "python" may be a different install)
set "PY=python"
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
%PY% -c "import pygame, numpy, serial" >nul 2>&1 || (
  echo Installing pygame-ce, numpy and pyserial...
  %PY% -m pip install -r requirements.txt
)
%PY% vault_runner.py %*
pause
