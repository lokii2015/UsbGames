/**
 * Redemption codes — created only after payment.
 * Regular: USB-XXXX-XXXX (48h default)
 * Gift:    USB-GXXX-XXXX (days — see GIFT_CODE_TTL_DAYS)
 */
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const { SUPPORT_EMAIL } = require("./support");

const DATA_DIR = path.join(__dirname, "data");
const CODES_FILE = path.join(DATA_DIR, "codes.json");
const CODE_TTL_MS =
  (Number(process.env.CODE_TTL_HOURS) > 0 ? Number(process.env.CODE_TTL_HOURS) : 48) *
  60 *
  60 *
  1000;
const GIFT_CODE_TTL_DAYS =
  Number(process.env.GIFT_CODE_TTL_DAYS) > 0 ? Number(process.env.GIFT_CODE_TTL_DAYS) : 7;
const GIFT_CODE_TTL_MS = GIFT_CODE_TTL_DAYS * 24 * 60 * 60 * 1000;
const GIFT_CODE_RE = /^USB-G[A-Z0-9]{4}-[A-Z0-9]{4}$/;
const STANDARD_CODE_RE = /^USB-[A-Z0-9]{4}-[A-Z0-9]{4}$/;

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

/** Gift codes: USB-GXXXX-XXXX — the G marks it as a gift */
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

function ttlMsForRow(row) {
  if (row?.isGift) return GIFT_CODE_TTL_MS;
  return CODE_TTL_MS;
}

function expiryLabelForRow(row) {
  if (row?.isGift) {
    const days = GIFT_CODE_TTL_DAYS;
    return days === 1 ? "1 day" : `${days} days`;
  }
  const hours = Math.round(CODE_TTL_MS / (60 * 60 * 1000));
  return hours === 1 ? "1 hour" : `${hours} hours`;
}

function expiresAtForRow(row) {
  if (row.expiresAt) return new Date(row.expiresAt).getTime();
  const created = row.createdAt ? new Date(row.createdAt).getTime() : 0;
  return created + ttlMsForRow(row);
}

function isExpired(row) {
  if (!row) return true;
  if (row.used) return false;
  return Date.now() > expiresAtForRow(row);
}

function findByOrderId(orderId) {
  const codes = load();
  const hit = Object.entries(codes).find(([, row]) => row.paypalOrderId === orderId);
  if (!hit) return null;
  if (isExpired(hit[1])) return null;
  return hit;
}

/** Only call after payment is confirmed — one code per order, valid 48 hours. */
function createForOrder({ orderId, productIds, email }) {
  const existing = findByOrderId(orderId);
  if (existing) return { code: existing[0], ...existing[1], existing: true };

  const codes = load();
  let code;
  do {
    code = generateCode();
  } while (codes[code]);

  const createdAt = new Date();
  const expiresAt = new Date(createdAt.getTime() + CODE_TTL_MS);

  const row = {
    productIds: [...productIds],
    email: String(email).trim().toLowerCase(),
    paypalOrderId: orderId,
    used: false,
    createdAt: createdAt.toISOString(),
    expiresAt: expiresAt.toISOString(),
  };
  codes[code] = row;
  save(codes);
  return { code, ...row, existing: false };
}

function redeem(codeRaw, emailRaw) {
  const code = normalizeCode(codeRaw);
  const email = String(emailRaw || "")
    .trim()
    .toLowerCase();
  if (!code || !email) {
    return { ok: false, error: "Enter your email and redemption code." };
  }

  const codes = load();
  const row = codes[code];
  if (!row) return { ok: false, error: "Invalid code." };
  if (row.used) return { ok: false, error: "This code was already used." };
  if (isExpired(row)) {
    return {
      ok: false,
      error: `This code expired (codes are valid for 48 hours after purchase). See refund.html and email ${SUPPORT_EMAIL} with your PayPal receipt.`,
      expired: true,
    };
  }
  if (row.email !== email) {
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
  createForOrder,
  findByOrderId,
  redeem,
  load,
  isExpired,
  CODE_TTL_MS,
};
