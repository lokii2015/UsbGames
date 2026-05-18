@echo off
cd /d "%~dp0"
echo Building BlockStack DX game.exe ...
pip install pygame pyinstaller pillow -q
python generate_icon.py
python -m PyInstaller --noconfirm --onefile --windowed --name game --icon=icon.png blockstack_dx_game.py
if exist "dist\game.exe" (
  move /Y "dist\game.exe" "game.exe"
  echo Done: game.exe
) else (
  echo Build failed. Use launch.bat with Python installed.
)
pause
