$games = @(
  @{ dir = "SnakeDeluxe"; script = "snake_deluxe_game.py" },
  @{ dir = "PixelFlapTurbo"; script = "pixel_flap_turbo_game.py" },
  @{ dir = "TicTacToeAIPlus"; script = "tictactoe_aiplus_game.py" }
)
$root = Join-Path $PSScriptRoot "..\PortableGames"
foreach ($g in $games) {
  $path = Join-Path $root $g.dir
  Set-Location $path
  Write-Host "Building $($g.dir)..."
  python -m PyInstaller --noconfirm --onefile --windowed --name game --icon=icon.png $($g.script) 2>&1
  if (Test-Path "dist\game.exe") { Move-Item -Force "dist\game.exe" "game.exe" }
}
Write-Host "Done."
