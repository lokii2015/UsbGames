@echo off
cd /d "%~dp0"
if exist game.exe (
  start "" game.exe
) else (
  python brick_breaker_game.py
)
