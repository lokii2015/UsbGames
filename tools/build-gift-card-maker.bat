@echo off
REM Build GiftCardMaker.exe (Windows) — requires Node.js once.
cd /d "%~dp0.."
if not exist "tools\dist" mkdir "tools\dist"
echo Installing pkg if needed...
call npx --yes pkg tools/gift-card-maker.js --targets node18-win-x64 --output tools/dist/GiftCardMaker.exe
if errorlevel 1 (
  echo Build failed. Run: npm install -g pkg
  exit /b 1
)
echo.
echo Built: tools\dist\GiftCardMaker.exe
echo Run: tools\dist\GiftCardMaker.exe 25 5
echo   (25 dollars CAD, 5 cards)
pause
