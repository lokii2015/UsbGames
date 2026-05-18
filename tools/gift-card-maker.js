#!/usr/bin/env node
/**
 * Create UsbGames gift cards (USB-Cxxx-xxxx-xxxx-x).
 * Usage:
 *   node tools/gift-card-maker.js 25 5
 *   node tools/gift-card-maker.js 25 5 --admin 5394
 * Writes to checkout/data/gift-cards.json (or --out path).
 */
const path = require("path");
const readline = require("readline");
const giftCards = require("../checkout/gift-cards");

const args = process.argv.slice(2);
let amountDollars = Number(args[0]);
let count = Number(args[1]) || 1;
let adminCode = "";
let outNote = "";

for (let i = 2; i < args.length; i++) {
  if (args[i] === "--admin" && args[i + 1]) {
    adminCode = args[++i];
  } else if (args[i] === "--note" && args[i + 1]) {
    outNote = args[++i];
  }
}

async function prompt(question) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => {
    rl.question(question, (ans) => {
      rl.close();
      resolve(ans.trim());
    });
  });
}

async function main() {
  if (!Number.isFinite(amountDollars) || amountDollars <= 0) {
    amountDollars = Number(await prompt("Amount in CAD (e.g. 25): "));
  }
  if (!Number.isFinite(count) || count < 1) {
    count = Number(await prompt("How many cards? "));
  }
  if (!adminCode) {
    adminCode = await prompt("Admin code (FAQ_ADMIN_CODE / GIFT_CARD_ADMIN_CODE): ");
  }

  const amountCents = Math.round(amountDollars * 100);
  const result = giftCards.createCards({
    amountCents,
    count,
    note: outNote || `Created ${new Date().toISOString()}`,
  });

  if (!result.ok) {
    console.error(result.error);
    process.exit(1);
  }

  console.log("\nUsbGames gift cards created\n");
  console.log("Amount each:", giftCards.formatMoney(result.amountCents));
  console.log("Count:", result.count);
  console.log("\nCodes:\n");
  result.codes.forEach((c) => console.log(c));
  console.log("\nSaved to checkout/data/gift-cards.json");
  console.log("Give these codes to customers — redeem at Checkout → Gift card tab.\n");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
