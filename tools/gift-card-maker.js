#!/usr/bin/env node
/**
 * UsbGames gift cards — USB-Cxxx-xxxx-xxxx-x
 *
 * STEP 1 — Print codes on cards (no money yet):
 *   node tools/gift-card-maker.js gen 15
 *   → saves tools/codes-to-print.txt
 *
 * STEP 2 — Link codes to CAD (activates on website):
 *   node tools/gift-card-maker.js link tools/codes-to-print.txt 25
 *   → every code gets $25.00 CAD
 *
 * Or file with amount per line:
 *   USB-C7YK-F8MA-HEYD-H 25
 *   USB-CABC-DEFG-HIJK-L 50
 *   node tools/gift-card-maker.js link tools/my-cards.txt
 *
 * Push local file to live site (Render):
 *   node tools/gift-card-maker.js push https://usbgames.onrender.com YOUR_ADMIN_CODE
 */
const fs = require("fs");
const path = require("path");
const readline = require("readline");
const giftCards = require("../checkout/gift-cards");

const ROOT = path.join(__dirname, "..");
const PRINT_FILE = path.join(__dirname, "codes-to-print.txt");
const DATA_FILE = path.join(ROOT, "checkout", "data", "gift-cards.json");

const args = process.argv.slice(2);
const cmd = (args[0] || "").toLowerCase();

function prompt(question) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => {
    rl.question(question, (ans) => {
      rl.close();
      resolve(ans.trim());
    });
  });
}

function parseCodesFile(filePath, defaultDollars) {
  const text = fs.readFileSync(filePath, "utf8");
  const entries = [];
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const parts = trimmed.split(/[\s,;\t]+/).filter(Boolean);
    if (!parts.length) continue;
    const code = parts[0];
    let dollars = defaultDollars;
    if (parts.length >= 2) {
      dollars = Number(parts[1].replace(/^\$/, ""));
    }
    entries.push({ code, amountDollars: dollars });
  }
  return entries;
}

async function cmdGen() {
  let count = Number(args[1]);
  if (!Number.isFinite(count) || count < 1) {
    count = Number(await prompt("How many codes to generate? "));
  }
  const codes = giftCards.generateCodesOnly(count);
  const lines = [
    "# UsbGames gift card codes — print these on your cards",
    "# Format: USB-Cxxx-xxxx-xxxx-x",
    "# Then run: node tools/gift-card-maker.js link tools/codes-to-print.txt AMOUNT",
    "",
    ...codes,
    "",
  ];
  fs.writeFileSync(PRINT_FILE, lines.join("\n"), "utf8");
  console.log("\nGenerated", codes.length, "codes (not active until you link)\n");
  codes.forEach((c) => console.log(c));
  console.log("\nSaved:", PRINT_FILE);
  console.log("\nNext: link amounts, e.g.");
  console.log("  node tools/gift-card-maker.js link tools/codes-to-print.txt 25\n");
}

async function cmdLink() {
  let filePath = args[1];
  let amountAll = Number(args[2]);

  if (!filePath) {
    filePath = await prompt("File with codes (e.g. tools/codes-to-print.txt): ");
  }
  if (!fs.existsSync(filePath)) {
    console.error("File not found:", filePath);
    process.exit(1);
  }

  const sample = fs.readFileSync(filePath, "utf8");
  const hasAmountsInline = sample.split(/\r?\n/).some((line) => {
    const p = line.trim().split(/\s+/);
    return p.length >= 2 && !Number.isNaN(Number(p[1]));
  });

  if (!hasAmountsInline && (!Number.isFinite(amountAll) || amountAll <= 0)) {
    amountAll = Number(await prompt("CAD amount for ALL codes in file (e.g. 25): "));
  }

  const entries = parseCodesFile(
    filePath,
    Number.isFinite(amountAll) && amountAll > 0 ? amountAll : null
  );

  if (!entries.length) {
    console.error("No codes found in file.");
    process.exit(1);
  }

  const result = giftCards.importCards(entries);
  if (!result.ok) {
    console.error(result.error);
    process.exit(1);
  }

  console.log("\nLinked", result.linked.length, "card(s) on this machine:\n");
  result.linked.forEach((r) => console.log(" ", r.code, "→", r.amountLabel));
  if (result.errors.length) {
    console.log("\nSkipped:");
    result.errors.forEach((e) => console.log(" ", e.code, e.error));
  }
  console.log("\nSaved:", DATA_FILE);
  console.log("\nFor LIVE site run:");
  console.log("  node tools/gift-card-maker.js push https://usbgames.onrender.com YOUR_ADMIN_CODE\n");
}

async function cmdPush() {
  let site = args[1] || "https://usbgames.onrender.com";
  let admin = args[2];
  if (!admin) {
    admin = await prompt("Admin code (FAQ_ADMIN_CODE from Render env): ");
  }

  if (!fs.existsSync(DATA_FILE)) {
    console.error("No local gift-cards.json — run link first.");
    process.exit(1);
  }
  const data = JSON.parse(fs.readFileSync(DATA_FILE, "utf8"));
  const cards = Object.entries(data).map(([code, row]) => ({
    code,
    amountDollars: (row.balanceCents || row.initialCents) / 100,
    overwrite: true,
  }));

  if (!cards.length) {
    console.error("No cards in local file.");
    process.exit(1);
  }

  const url = site.replace(/\/$/, "") + "/api/gift-card/admin/link";
  console.log("Pushing", cards.length, "cards to", url, "...");

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ adminCode: admin, cards }),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    console.error(body.error || res.statusText);
    process.exit(1);
  }
  console.log("\nLive site updated:", body.count, "card(s)");
  if (body.errors?.length) {
    console.log("Errors:", body.errors);
  }
}

async function main() {
  if (cmd === "gen" || cmd === "generate") {
    await cmdGen();
    return;
  }
  if (cmd === "link") {
    await cmdLink();
    return;
  }
  if (cmd === "push") {
    await cmdPush();
    return;
  }

  console.log(`
UsbGames Gift Card Maker — USB-Cxxx-xxxx-xxxx-x

  gen 15              Generate 15 codes → tools/codes-to-print.txt
  link FILE 25        Link every code in FILE to $25 CAD (local + ready to push)
  link FILE           FILE has "CODE 25" per line (different amounts OK)
  push SITE CODE      Copy local gift-cards.json to live Render site

Examples:
  node tools/gift-card-maker.js gen 15
  node tools/gift-card-maker.js link tools/codes-to-print.txt 25
  node tools/gift-card-maker.js push https://usbgames.onrender.com 5394
`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
