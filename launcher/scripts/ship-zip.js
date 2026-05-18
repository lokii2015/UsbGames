/**
 * USB bundle ZIP:
 *   UsbGames/
 *     UsbGames.exe
 *     (app files: dlls, resources, …)
 *     PortableGames/
 *
 * Everything stays on the USB — nothing in AppData.
 */
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const launcherDir = path.join(__dirname, "..");
const webRoot = path.join(launcherDir, "..");
const distDir = path.join(launcherDir, "dist");
const unpacked = path.join(distDir, "win-unpacked");
const pgSrc = path.join(launcherDir, "PortableGames");
const bundleName = "UsbGames";

if (!fs.existsSync(unpacked)) {
  console.error("Run npm run pack:win first. Missing dist/win-unpacked.");
  process.exit(1);
}

const stagingParent = path.join(launcherDir, "staging-zip");
const bundleDir = path.join(stagingParent, bundleName);
const archiveBundle = path.join(webRoot, "archive", bundleName);
const outZip = path.join(webRoot, "UsbGames-Launcher.zip");
const oldExe = path.join(webRoot, "UsbGames.exe");

if (fs.existsSync(stagingParent)) {
  fs.rmSync(stagingParent, { recursive: true, force: true });
}
fs.mkdirSync(bundleDir, { recursive: true });

fs.cpSync(unpacked, bundleDir, { recursive: true });
fs.cpSync(pgSrc, path.join(bundleDir, "PortableGames"), { recursive: true });

if (fs.existsSync(path.join(webRoot, "archive"))) {
  fs.rmSync(path.join(webRoot, "archive"), { recursive: true, force: true });
}
fs.mkdirSync(path.dirname(archiveBundle), { recursive: true });
fs.cpSync(bundleDir, archiveBundle, { recursive: true });

if (fs.existsSync(oldExe)) {
  try {
    fs.unlinkSync(oldExe);
  } catch {
    console.warn("Remove old", oldExe, "manually if you still see it.");
  }
}

if (fs.existsSync(outZip)) fs.unlinkSync(outZip);

try {
  execFileSync(
    "tar",
    ["-a", "-c", "-f", outZip, "-C", stagingParent, bundleName],
    { stdio: "inherit" }
  );
} catch {
  const ps = `Compress-Archive -Path '${bundleDir.replace(
    /'/g,
    "''"
  )}' -DestinationPath '${outZip.replace(/'/g, "''")}' -Force`;
  execFileSync("powershell.exe", ["-NoProfile", "-Command", ps], {
    stdio: "inherit",
  });
}

fs.rmSync(stagingParent, { recursive: true, force: true });
console.log("Wrote", outZip);
console.log("Wrote", archiveBundle);
console.log("Unzip to USB, then run UsbGames\\UsbGames.exe");
