@echo off
cd /d "%~dp0"
if exist "game.exe" (
  start "" "game.exe"
  exit /b 0
)
where pythonw >nul 2>&1
if %errorlevel%==0 (
  start "" pythonw "%~dp0snake_game.py"
  exit /b 0
)
where python >nul 2>&1
if %errorlevel%==0 (
  start "" python "%~dp0snake_game.py"
  exit /b 0
)
echo Install Python and pygame, or run build.bat to create game.exe.
pause
