/**
 * Store credit gift cards — format USB-Cxxx-xxxx-xxxx-x (checkout only).
 */
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const DATA_DIR = path.join(__dirname, "data");
const FILE = path.join(DATA_DIR, "gift-cards.json");
const GIFT_CARD_RE = /^USB-C[A-Z0-9]{3}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]$/;

function ensureDir() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
}

function load() {
  ensureDir();
  if (!fs.existsSync(FILE)) return {};
  try {
    return JSON.parse(fs.readFileSync(FILE, "utf8"));
  } catch {
    return {};
  }
}

function save(data) {
  ensureDir();
  fs.writeFileSync(FILE, JSON.stringify(data, null, 2));
}

function normalizeCode(raw) {
  return String(raw || "")
    .trim()
    .toUpperCase()
    .replace(/\s+/g, "");
}

function isValidFormat(code) {
  return GIFT_CARD_RE.test(normalizeCode(code));
}

function randomChunk(len) {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  let out = "";
  const bytes = crypto.randomBytes(len);
  for (let i = 0; i < len; i++) {
    out += chars[bytes[i] % chars.length];
  }
  return out;
}

function generateCode() {
  return `USB-C${randomChunk(3)}-${randomChunk(4)}-${randomChunk(4)}-${randomChunk(1)}`;
}

function formatMoney(cents, currency) {
  const cur = (currency || "cad").toUpperCase();
  return `$${(cents / 100).toFixed(2)} ${cur}`;
}

function getRow(codeRaw) {
  const code = normalizeCode(codeRaw);
  if (!isValidFormat(code)) return null;
  const row = load()[code];
  if (!row) return null;
  return { code, row };
}

function getBalance(codeRaw) {
  const hit = getRow(codeRaw);
  if (!hit) {
    return { ok: false, error: "Invalid gift card. Format: USB-Cxxx-xxxx-xxxx-x" };
  }
  if (hit.row.disabled) {
    return { ok: false, error: "This gift card is no longer active." };
  }
  const balanceCents = Math.max(0, Number(hit.row.balanceCents) || 0);
  return {
    ok: true,
    code: hit.code,
    balanceCents,
    initialCents: hit.row.initialCents,
    currency: hit.row.currency || "cad",
    balanceLabel: formatMoney(balanceCents, hit.row.currency),
    initialLabel: formatMoney(hit.row.initialCents, hit.row.currency),
    createdAt: hit.row.createdAt,
  };
}

function quoteForCart(codeRaw, cartAmountCents) {
  const bal = getBalance(codeRaw);
  if (!bal.ok) return bal;
  const total = Math.max(0, Number(cartAmountCents) || 0);
  const appliedCents = Math.min(bal.balanceCents, total);
  const remainderCents = total - appliedCents;
  return {
    ok: true,
    code: bal.code,
    balanceCents: bal.balanceCents,
    balanceAfterCents: bal.balanceCents - appliedCents,
    appliedCents,
    remainderCents,
    currency: bal.currency,
    balanceLabel: bal.balanceLabel,
    appliedLabel: formatMoney(appliedCents, bal.currency),
    remainderLabel: formatMoney(remainderCents, bal.currency),
    balanceAfterLabel: formatMoney(bal.balanceCents - appliedCents, bal.currency),
  };
}

function createCards({ amountCents, count, note }) {
  const cents = Math.round(Number(amountCents));
  if (!Number.isFinite(cents) || cents < 1) {
    return { ok: false, error: "Amount must be at least $0.01." };
  }
  const n = Math.min(500, Math.max(1, Math.round(Number(count) || 1)));
  const data = load();
  const codes = [];
  const now = new Date().toISOString();

  for (let i = 0; i < n; i++) {
    let code;
    do {
      code = generateCode();
    } while (data[code]);

    data[code] = {
      balanceCents: cents,
      initialCents: cents,
      currency: "cad",
      createdAt: now,
      note: String(note || "").slice(0, 200) || null,
      uses: [],
    };
    codes.push(code);
  }
  save(data);
  return { ok: true, codes, amountCents: cents, count: n };
}

function deduct(codeRaw, amountCents, orderId) {
  const use = Math.round(Number(amountCents));
  if (!Number.isFinite(use) || use < 1) {
    return { ok: false, error: "Invalid gift card amount." };
  }
  const code = normalizeCode(codeRaw);
  const data = load();
  const row = data[code];
  if (!row) return { ok: false, error: "Invalid gift card." };
  if (row.disabled) return { ok: false, error: "This gift card is no longer active." };

  const balance = Math.max(0, Number(row.balanceCents) || 0);
  if (use > balance) {
    return {
      ok: false,
      error: `Gift card only has ${formatMoney(balance, row.currency)} left.`,
    };
  }

  row.balanceCents = balance - use;
  row.uses = Array.isArray(row.uses) ? row.uses : [];
  row.uses.push({
    orderId: String(orderId || ""),
    amountCents: use,
    at: new Date().toISOString(),
  });
  data[code] = row;
  save(data);

  return {
    ok: true,
    code,
    usedCents: use,
    balanceCents: row.balanceCents,
    balanceLabel: formatMoney(row.balanceCents, row.currency),
  };
}

module.exports = {
  GIFT_CARD_RE,
  normalizeCode,
  isValidFormat,
  generateCode,
  getBalance,
  quoteForCart,
  createCards,
  deduct,
  formatMoney,
};
