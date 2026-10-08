@echo off
rem Flies the game on its own, with no launcher: keyboard, USB pad or one cabled Arduino.
cd /d "%~dp0"
set "PY=python"
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
%PY% -c "import pygame, numpy, serial" >nul 2>&1 || (
  echo Installing pygame-ce, numpy and pyserial...
  %PY% -m pip install -r requirements.txt
)
%PY% drone_sim.py %*
pause
