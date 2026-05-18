@echo off
cd /d "%~dp0"
if exist game.exe (
  start "" game.exe
) else (
  python memory_match_game.py
)
