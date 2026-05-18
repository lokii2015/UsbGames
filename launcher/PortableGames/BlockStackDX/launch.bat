@echo off
cd /d "%~dp0"
if exist game.exe (
  start "" game.exe
) else (
  python blockstack_dx_game.py
)
