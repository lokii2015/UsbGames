# Rebuild game.exe for every PortableGames title (after profile / gameplay changes).
$ErrorActionPreference = "Stop"
$pg = Join-Path $PSScriptRoot "..\PortableGames"
Get-ChildItem $pg -Directory | ForEach-Object {
  $bat = Join-Path $_.FullName "build.bat"
  if (Test-Path $bat) {
    Write-Host "Building $($_.Name)..."
    Push-Location $_.FullName
    cmd /c build.bat
    Pop-Location
  }
}
Write-Host "Done."
