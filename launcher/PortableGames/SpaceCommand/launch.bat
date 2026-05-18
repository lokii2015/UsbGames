@echo off
cd /d "%~dp0"
if exist game.exe (
  start "" game.exe
) else (
  python space_command_game.py
)
