@echo off
rem One-time: download the real 3D assets (~300 MB) and build game-ready versions.
cd /d "%~dp0"
set "GODOT=C:\Tools\Godot_v4.7.2-stable_win64_console.exe"
if not "%1"=="" set "GODOT=%1"
python fetch_assets.py || goto :err
"%GODOT%" --headless --path godot --import
"%GODOT%" --headless --path godot --script res://tools/optimize.gd
echo Assets ready.
goto :eof
:err
echo Asset download failed - check your internet connection and run again.
pause
