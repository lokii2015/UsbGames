const { app, BrowserWindow, ipcMain, shell } = require("electron");
const path = require("path");
const fs = require("fs");
const { spawn } = require("child_process");

/** Folder where UsbGames.exe lives (your USB stick path when installed). */
function usbRoot() {
  if (app.isPackaged) {
    return path.dirname(process.execPath);
  }
  return __dirname;
}

if (app.isPackaged) {
  app.setPath("userData", path.join(usbRoot(), "UsbGames"));
}

function portableGamesRoot() {
  return path.join(usbRoot(), "PortableGames");
}

function ensurePortableGamesRoot() {
  const root = portableGamesRoot();
  if (!fs.existsSync(root)) {
    try {
      fs.mkdirSync(root, { recursive: true });
    } catch {
      /* ignore */
    }
  }
  return root;
}

function iconToDataUrl(iconPath) {
  if (!iconPath || !fs.existsSync(iconPath)) return null;
  try {
    const buf = fs.readFileSync(iconPath);
    const ext = path.extname(iconPath).toLowerCase();
    const mime =
      ext === ".png"
        ? "image/png"
        : ext === ".jpg" || ext === ".jpeg"
          ? "image/jpeg"
          : "image/png";
    return `data:${mime};base64,${buf.toString("base64")}`;
  } catch {
    return null;
  }
}

const PREFERRED_EXE = [
  "game.exe",
  "launch.exe",
  "play.exe",
  "start.exe",
  "run.exe",
  "main.exe",
];

const LAUNCH_BAT = ["launch.bat", "run.bat", "play.bat", "start.bat"];

/**
 * Collect .exe paths under dir up to maxDepth (0 = files in dir only).
 */
function collectExés(dir, maxDepth) {
  const out = [];
  function walk(d, depth) {
    if (depth > maxDepth) return;
    let entries;
    try {
      entries = fs.readdirSync(d, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      const p = path.join(d, e.name);
      if (e.isDirectory()) {
        walk(p, depth + 1);
      } else if (e.isFile() && e.name.toLowerCase().endsWith(".exe")) {
        out.push(p);
      }
    }
  }
  walk(dir, 0);
  return out;
}

function pickExecutable(gameDir) {
  const exes = collectExés(gameDir, 2);
  if (exes.length) {
    const lower = (p) => path.basename(p).toLowerCase();
    for (const pref of PREFERRED_EXE) {
      const hit = exes.find((x) => lower(x) === pref);
      if (hit) return { path: hit, kind: "exe" };
    }
    exes.sort((a, b) => lower(a).localeCompare(lower(b)));
    return { path: exes[0], kind: "exe" };
  }
  for (const name of LAUNCH_BAT) {
    const p = path.join(gameDir, name);
    if (fs.existsSync(p)) return { path: p, kind: "bat" };
  }
  return null;
}

function readGameJson(gameDir) {
  const p = path.join(gameDir, "game.json");
  if (!fs.existsSync(p)) return null;
  try {
    const raw = fs.readFileSync(p, "utf8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function readNameFile(gameDir, folderName) {
  const meta = readGameJson(gameDir);
  if (meta && typeof meta.name === "string" && meta.name.trim()) {
    return meta.name.trim();
  }
  const nameFile = path.join(gameDir, "name");
  let raw = "";
  if (fs.existsSync(nameFile)) {
    try {
      raw = fs.readFileSync(nameFile, "utf8");
    } catch {
      raw = "";
    }
  }
  if (raw && raw.charCodeAt(0) === 0xfeff) raw = raw.slice(1);
  const line = raw.trim().split(/\r?\n/)[0] || "";
  return line || folderName;
}

function scanGames() {
  const root = ensurePortableGamesRoot();
  if (!fs.existsSync(root)) {
    return {
      games: [],
      root: portableGamesRoot(),
      error: "Could not create PortableGames folder.",
    };
  }

  const games = [];
  let entries;
  try {
    entries = fs.readdirSync(root, { withFileTypes: true });
  } catch {
    return { games: [], root, error: "Cannot read PortableGames folder." };
  }

  for (const ent of entries) {
    if (!ent.isDirectory()) continue;
    const dir = path.join(root, ent.name);
    const displayName = readNameFile(dir, ent.name);

    let iconPath = null;
    for (const n of ["icon.png", "icon.jpg", "icon.jpeg"]) {
      const p = path.join(dir, n);
      if (fs.existsSync(p)) {
        iconPath = p;
        break;
      }
    }

    const launch = pickExecutable(dir);

    const meta = readGameJson(dir);
    let description = "No description yet.";
    if (meta && typeof meta.description === "string" && meta.description.trim()) {
      description = meta.description.trim();
    } else {
      const descPath = path.join(dir, "description.txt");
      if (fs.existsSync(descPath)) {
        try {
          let t = fs.readFileSync(descPath, "utf8").trim();
          if (t.charCodeAt(0) === 0xfeff) t = t.slice(1);
          if (t) description = t;
        } catch {
          /* keep default */
        }
      }
    }

    games.push({
      id: ent.name,
      name: displayName,
      iconDataUrl: iconToDataUrl(iconPath),
      description,
      exePath: launch ? launch.path : null,
      launchKind: launch ? launch.kind : null,
      hasExecutable: !!launch,
    });
  }

  games.sort((a, b) =>
    String(a.name).localeCompare(String(b.name), undefined, {
      sensitivity: "base",
    })
  );
  return { games, root, error: null };
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1024,
    height: 640,
    minWidth: 860,
    minHeight: 520,
    backgroundColor: "#0f0f14",
    title: "UsbGames",
    icon: path.join(__dirname, "build", "icon.ico"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.setMenuBarVisibility(false);
  win.loadFile(path.join(__dirname, "index.html"));
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

ipcMain.handle("scan-games", () => scanGames());

ipcMain.handle("launch-game", (_e, targetPath, launchKind) => {
  if (!targetPath || !fs.existsSync(targetPath)) {
    return { ok: false, message: "No launch file in this game folder." };
  }
  const cwd = path.dirname(targetPath);
  const isBat =
    launchKind === "bat" || targetPath.toLowerCase().endsWith(".bat");
  try {
    if (isBat) {
      spawn(process.env.ComSpec || "cmd.exe", ["/c", targetPath], {
        detached: true,
        stdio: "ignore",
        cwd,
      }).unref();
    } else {
      spawn(targetPath, [], {
        detached: true,
        stdio: "ignore",
        cwd,
      }).unref();
    }
    return { ok: true };
  } catch (err) {
    return { ok: false, message: err.message || "Could not start game." };
  }
});

ipcMain.handle("open-games-folder", () => {
  const root = ensurePortableGamesRoot();
  shell.openPath(root);
});

