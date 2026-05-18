@echo off
cd /d "%~dp0"
if exist game.exe (
  start "" game.exe
) else (
  python pixel_chomp_game.py
)
