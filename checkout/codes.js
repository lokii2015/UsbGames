/**
 * Redemption codes — created only after payment.
 * Regular: USB-XXXX-XXXX
 * Gift:    USB-GXXX-XXXX
 */
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const { SUPPORT_EMAIL } = require("./support");
const {
  normalizeEmail,
  emailsEquivalent,
  collectEmails,
  rowLookupEmails,
  emailMatchesAny,
} = require("./email-match");
const pending = require("./pending-orders");

const DATA_DIR = path.join(__dirname, "data");
const CODES_FILE = path.join(DATA_DIR, "codes.json");
const GIFT_CODE_RE = /^USB-G[A-Z0-9]{4}-[A-Z0-9]{4}$/;
const STANDARD_CODE_RE = /^USB-(?!G[A-Z0-9]{3}-)[A-Z0-9]{4}-[A-Z0-9]{4}$/;

function ensureDir() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
}

function load() {
  ensureDir();
  if (!fs.existsSync(CODES_FILE)) return {};
  try {
    return JSON.parse(fs.readFileSync(CODES_FILE, "utf8"));
  } catch {
    return {};
  }
}

function save(codes) {
  ensureDir();
  fs.writeFileSync(CODES_FILE, JSON.stringify(codes, null, 2));
}

function normalizeCode(raw) {
  return String(raw || "")
    .trim()
    .toUpperCase()
    .replace(/\s+/g, "");
}

function generateCode() {
  const a = crypto.randomBytes(2).toString("hex").toUpperCase();
  const b = crypto.randomBytes(2).toString("hex").toUpperCase();
  return `USB-${a}-${b}`;
}

/** Gift codes: USB-GXXXX-XXXX */
function generateGiftCode() {
  const a = crypto.randomBytes(2).toString("hex").toUpperCase();
  const b = crypto.randomBytes(2).toString("hex").toUpperCase();
  return `USB-G${a}-${b}`;
}

function isGiftCode(code) {
  return GIFT_CODE_RE.test(normalizeCode(code));
}

function isValidCodeFormat(code) {
  const c = normalizeCode(code);
  return GIFT_CODE_RE.test(c) || STANDARD_CODE_RE.test(c);
}

function isExpired() {
  return false;
}

function findByOrderId(orderId) {
  const codes = load();
  const hit = Object.entries(codes).find(([, row]) => row.paypalOrderId === orderId);
  if (!hit) return null;
  return hit;
}

/** Only call after payment is confirmed — one code per order. */
function createForOrder({ orderId, productIds, email, isGift, buyerEmail, lookupEmails }) {
  const existing = findByOrderId(orderId);
  if (existing) return { code: existing[0], ...existing[1], existing: true };

  const codes = load();
  const gift = Boolean(isGift);
  let code;
  do {
    code = gift ? generateGiftCode() : generateCode();
  } while (codes[code]);

  const row = {
    productIds: [...productIds],
    email: normalizeEmail(email),
    paypalOrderId: orderId,
    used: false,
    isGift: gift,
    createdAt: new Date().toISOString(),
  };
  if (gift && buyerEmail) {
    row.buyerEmail = normalizeEmail(buyerEmail);
  }
  row.lookupEmails = collectEmails(row.email, row.buyerEmail, lookupEmails);
  codes[code] = row;
  save(codes);
  return { code, ...row, existing: false };
}

function rowMatchesEmail(row, searchEmail) {
  const pend = row.paypalOrderId ? pending.get(row.paypalOrderId) : null;
  const emails = rowLookupEmails(row, pend);
  return emailMatchesAny(searchEmail, emails);
}

/** Orders tied to this email (checkout, PayPal, gift buyer, Gmail aliases). */
function listByEmail(emailRaw) {
  const email = normalizeEmail(emailRaw);
  if (!email) return [];

  const all = load();
  const out = [];
  for (const [code, row] of Object.entries(all)) {
    if (!rowMatchesEmail(row, email)) continue;
    const asRecipient = emailsEquivalent(row.email, email);
    const asBuyer = row.buyerEmail && emailsEquivalent(row.buyerEmail, email);
    out.push({
      code,
      productIds: row.productIds || [],
      purchasedAt: row.createdAt,
      redeemed: Boolean(row.used),
      redeemedAt: row.redeemedAt || null,
      isGift: Boolean(row.isGift),
      role:
        asBuyer && !asRecipient
          ? "buyer"
          : asRecipient && row.isGift
            ? "recipient"
            : "owner",
      paypalOrderId: row.paypalOrderId || null,
    });
  }
  out.sort((a, b) => new Date(b.purchasedAt) - new Date(a.purchasedAt));
  return out;
}

function findOwnedCode(emailRaw, codeRaw) {
  const email = normalizeEmail(emailRaw);
  const code = normalizeCode(codeRaw);
  if (!email || !code) return null;
  const row = load()[code];
  if (!row) return null;
  if (!rowMatchesEmail(row, email)) return null;
  return { code, row };
}

function redeem(codeRaw, emailRaw) {
  const code = normalizeCode(codeRaw);
  const email = String(emailRaw || "")
    .trim()
    .toLowerCase();
  if (!code || !email) {
    return { ok: false, error: "Enter your email and redemption code." };
  }

  if (!isValidCodeFormat(code)) {
    return {
      ok: false,
      error:
        "Invalid code format. Regular codes look like USB-XXXX-XXXX. Gift codes look like USB-GXXX-XXXX.",
    };
  }

  const codes = load();
  const row = codes[code];
  if (!row) return { ok: false, error: "Invalid code." };
  if (row.used) return { ok: false, error: "This code was already used." };
  if (!rowMatchesEmail(row, email)) {
    return {
      ok: false,
      error:
        "Email does not match this code. Use the same email the code was sent to.",
    };
  }

  row.used = true;
  row.redeemedAt = new Date().toISOString();
  codes[code] = row;
  save(codes);

  return { ok: true, code, productIds: row.productIds, email: row.email };
}

module.exports = {
  normalizeCode,
  normalizeEmail,
  isGiftCode,
  isValidCodeFormat,
  createForOrder,
  findByOrderId,
  redeem,
  load,
  listByEmail,
  findOwnedCode,
  rowMatchesEmail,
  isExpired,
};
