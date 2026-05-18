/**
 * Zip each PortableGames folder for the website downloads/ folder.
 * Includes only files needed to play (no source/build artifacts).
 */
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const launcherDir = path.join(__dirname, "..");
const webRoot = path.join(launcherDir, "..");
const pgRoot = path.join(launcherDir, "PortableGames");
const outDir = path.join(webRoot, "downloads");
const checkoutPremiumDir = path.join(webRoot, "checkout", "downloads");
const staging = path.join(launcherDir, "staging-games");

const FREE_GAMES = [
  "Snake",
  "TicTacToe",
  "PixelFlap",
  "BrickBreaker",
  "SpaceCommand",
  "MemoryMatch",
  "Pong",
];
const PREMIUM_GAMES = [
  "BlackJack",
  "SnakeDeluxe",
  "PixelFlapTurbo",
  "TicTacToeAIPlus",
  "GridDefense",
  "PixelKart",
  "PocketRPG",
  "BlockStackDX",
  "PixelChomp",
];
const STARTER_PACK_GAMES = ["SnakeDeluxe", "PixelFlapTurbo", "TicTacToeAIPlus"];
const RETRO_ARCADE_PACK_GAMES = ["GridDefense", "PixelKart", "PocketRPG"];
const GAMES = [...FREE_GAMES, ...PREMIUM_GAMES];

const INCLUDE_FILES = new Set([
  "game.exe",
  "game.json",
  "icon.png",
  "name",
  "description.txt",
  "launch.bat",
  "usbgames_profile.py",
]);

const SHARED_PROFILE = path.join(pgRoot, "_shared", "usbgames_profile.py");

function shouldInclude(relPath) {
  const base = path.basename(relPath);
  if (INCLUDE_FILES.has(base)) return true;
  if (relPath.replace(/\\/g, "/").startsWith("assets/")) return true;
  return false;
}

function markWebProfile(stageGameDir) {
  if (fs.existsSync(SHARED_PROFILE)) {
    fs.copyFileSync(SHARED_PROFILE, path.join(stageGameDir, "usbgames_profile.py"));
  }
  const metaPath = path.join(stageGameDir, "game.json");
  let meta = {};
  if (fs.existsSync(metaPath)) {
    try {
      meta = JSON.parse(fs.readFileSync(metaPath, "utf8"));
    } catch {
      meta = {};
    }
  }
  meta.profile = "web";
  fs.writeFileSync(metaPath, JSON.stringify(meta, null, 2));
}

function copyGameFiles(srcDir, destDir) {
  fs.mkdirSync(destDir, { recursive: true });
  function walk(sub) {
    const full = path.join(srcDir, sub);
    const entries = fs.readdirSync(full, { withFileTypes: true });
    for (const e of entries) {
      const rel = sub ? `${sub}/${e.name}` : e.name;
      if (e.isDirectory()) {
        if (e.name === "assets" || rel.startsWith("assets")) {
          const destSub = path.join(destDir, rel);
          fs.mkdirSync(destSub, { recursive: true });
          walk(rel);
        }
        continue;
      }
      if (!shouldInclude(rel)) continue;
      const dest = path.join(destDir, rel);
      fs.mkdirSync(path.dirname(dest), { recursive: true });
      fs.copyFileSync(path.join(full, e.name), dest);
    }
  }
  walk("");
}

if (!fs.existsSync(pgRoot)) {
  console.error("Missing PortableGames at", pgRoot);
  process.exit(1);
}

fs.mkdirSync(outDir, { recursive: true });
fs.mkdirSync(checkoutPremiumDir, { recursive: true });
const imagesDir = path.join(webRoot, "images", "games");
fs.mkdirSync(imagesDir, { recursive: true });

if (fs.existsSync(staging)) {
  fs.rmSync(staging, { recursive: true, force: true });
}

for (const game of GAMES) {
  const src = path.join(pgRoot, game);
  if (!fs.existsSync(src)) {
    console.warn("Skip missing game:", game);
    continue;
  }

  const iconSrc = path.join(src, "icon.png");
  if (fs.existsSync(iconSrc)) {
    fs.copyFileSync(iconSrc, path.join(imagesDir, `${game.toLowerCase()}.png`));
  }

  const stageGame = path.join(staging, game);
  copyGameFiles(src, stageGame);

  markWebProfile(stageGame);

  if (!fs.existsSync(path.join(stageGame, "game.exe"))) {
    console.warn(game, "— no game.exe in package (build the game first)");
  }

  const outZip = path.join(outDir, `${game}.zip`);
  if (fs.existsSync(outZip)) fs.unlinkSync(outZip);

  try {
    execFileSync(
      "tar",
      ["-a", "-c", "-f", outZip, "-C", staging, game],
      { stdio: "inherit" }
    );
  } catch {
    const ps = `Compress-Archive -Path '${stageGame.replace(
      /'/g,
      "''"
    )}' -DestinationPath '${outZip.replace(/'/g, "''")}' -Force`;
    execFileSync("powershell.exe", ["-NoProfile", "-Command", ps], {
      stdio: "inherit",
    });
  }
  console.log("Wrote", outZip);
}

// Starter Pack: all premium titles in one zip
const packStaging = path.join(staging, "StarterPack");
fs.mkdirSync(packStaging, { recursive: true });
for (const game of STARTER_PACK_GAMES) {
  const src = path.join(pgRoot, game);
  if (!fs.existsSync(src)) continue;
  const dest = path.join(packStaging, game);
  copyGameFiles(src, dest);
  markWebProfile(dest);
}
const starterReadme = path.join(packStaging, "README.txt");
fs.writeFileSync(
  starterReadme,
  "UsbGames Starter Pack — unzip each folder into UsbGames\\PortableGames\\\n",
  "utf8"
);
const starterZip = path.join(outDir, "UsbGames-StarterPack.zip");
if (fs.existsSync(starterZip)) fs.unlinkSync(starterZip);
try {
  execFileSync("tar", ["-a", "-c", "-f", starterZip, "-C", staging, "StarterPack"], {
    stdio: "inherit",
  });
} catch {
  const ps = `Compress-Archive -Path '${packStaging.replace(
    /'/g,
    "''"
  )}\\*' -DestinationPath '${starterZip.replace(/'/g, "''")}' -Force`;
  execFileSync("powershell.exe", ["-NoProfile", "-Command", ps], { stdio: "inherit" });
}
console.log("Wrote", starterZip);

// Retro Arcade Pack: Grid Defense + Pixel Kart + Pocket RPG
const retroStaging = path.join(staging, "RetroArcadePack");
fs.mkdirSync(retroStaging, { recursive: true });
for (const game of RETRO_ARCADE_PACK_GAMES) {
  const src = path.join(pgRoot, game);
  if (!fs.existsSync(src)) continue;
  const dest = path.join(retroStaging, game);
  copyGameFiles(src, dest);
  markWebProfile(dest);
}
const retroReadme = path.join(retroStaging, "README.txt");
fs.writeFileSync(
  retroReadme,
  "UsbGames Retro Arcade Pack — unzip each folder into UsbGames\\PortableGames\\\n" +
    "Includes: GridDefense, PixelKart, PocketRPG\n",
  "utf8"
);
const retroZip = path.join(outDir, "UsbGames-RetroArcadePack.zip");
if (fs.existsSync(retroZip)) fs.unlinkSync(retroZip);
try {
  execFileSync("tar", ["-a", "-c", "-f", retroZip, "-C", staging, "RetroArcadePack"], {
    stdio: "inherit",
  });
} catch {
  const ps = `Compress-Archive -Path '${retroStaging.replace(
    /'/g,
    "''"
  )}\\*' -DestinationPath '${retroZip.replace(/'/g, "''")}' -Force`;
  execFileSync("powershell.exe", ["-NoProfile", "-Command", ps], { stdio: "inherit" });
}
console.log("Wrote", retroZip);

for (const name of [
  "SnakeDeluxe.zip",
  "PixelFlapTurbo.zip",
  "TicTacToeAIPlus.zip",
  "GridDefense.zip",
  "PixelKart.zip",
  "PocketRPG.zip",
  "BlockStackDX.zip",
  "PixelChomp.zip",
  "BlackJack.zip",
  "UsbGames-StarterPack.zip",
  "UsbGames-RetroArcadePack.zip",
]) {
  const src = path.join(outDir, name);
  if (!fs.existsSync(src)) continue;
  fs.copyFileSync(src, path.join(checkoutPremiumDir, name));
  console.log("Copied premium zip to checkout/downloads/", name);
}

fs.rmSync(staging, { recursive: true, force: true });
console.log("Game icons copied to images/games/");
