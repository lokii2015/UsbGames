@echo off
cd /d "%~dp0"
if exist game.exe (
  start "" game.exe
) else (
  python blackjack_game.py
)
