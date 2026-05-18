@echo off
title UsbGames site
cd /d "%~dp0checkout"
echo Starting UsbGames at http://localhost:4242
echo FAQ admin code is in checkout\.env (FAQ_ADMIN_CODE)
echo.
start "" "http://localhost:4242/"
npm start
