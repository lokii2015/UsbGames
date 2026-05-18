/**
 * Builds build/icon.ico from site logo.svg for electron-builder.
 */
const fs = require("fs");
const path = require("path");

const buildDir = path.join(__dirname, "..", "build");
const logoSvg = path.join(__dirname, "..", "..", "logo.svg");
const pngPath = path.join(buildDir, "icon.png");
const icoPath = path.join(buildDir, "icon.ico");

if (!fs.existsSync(logoSvg)) {
  console.error("logo.svg not found at", logoSvg);
  process.exit(1);
}

fs.mkdirSync(buildDir, { recursive: true });

async function main() {
  const sharp = require("sharp");
  const pngToIco = require("png-to-ico");

  await sharp(logoSvg)
    .resize(256, 256, {
      fit: "contain",
      background: { r: 15, g: 15, b: 20, alpha: 0 },
    })
    .png()
    .toFile(pngPath);

  const buf = await pngToIco(pngPath);
  fs.writeFileSync(icoPath, buf);
  console.log("Wrote", icoPath);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
