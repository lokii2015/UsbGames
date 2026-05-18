/**
 * Purchase history — email magic-link access (no accounts).
 */
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const codes = require("./codes");
const { normalizeEmail, emailMatchesAny } = require("./email-match");

const DATA_DIR = path.join(__dirname, "data");
const SESSIONS_FILE = path.join(DATA_DIR, "purchase-history-sessions.json");
const PURCHASES_FILE = path.join(DATA_DIR, "purchases.json");
const TOKEN_HOURS = 2;
const REQUEST_COOLDOWN_MS = 60 * 1000;
const MAX_REQUESTS_PER_HOUR = 5;

function ensureDir() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
}

function isValidEmail(email) {
  const em = normalizeEmail(email);
  return em && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(em);
}

function loadStore() {
  ensureDir();
  if (!fs.existsSync(SESSIONS_FILE)) {
    return { sessions: {}, requests: {} };
  }
  try {
    const raw = JSON.parse(fs.readFileSync(SESSIONS_FILE, "utf8"));
    return {
      sessions: raw.sessions && typeof raw.sessions === "object" ? raw.sessions : {},
      requests:
        raw.requests && typeof raw.requests === "object" ? raw.requests : {},
    };
  } catch {
    return { sessions: {}, requests: {} };
  }
}

function saveStore(data) {
  ensureDir();
  fs.writeFileSync(SESSIONS_FILE, JSON.stringify(data, null, 2));
}

function loadPurchases() {
  ensureDir();
  if (!fs.existsSync(PURCHASES_FILE)) return {};
  try {
    return JSON.parse(fs.readFileSync(PURCHASES_FILE, "utf8"));
  } catch {
    return {};
  }
}

function pruneSessions(sessions) {
  const now = Date.now();
  for (const key of Object.keys(sessions)) {
    if (new Date(sessions[key].expiresAt).getTime() < now) {
      delete sessions[key];
    }
  }
}

function pruneRequests(requests) {
  const hourAgo = Date.now() - 60 * 60 * 1000;
  for (const key of Object.keys(requests)) {
    requests[key] = (requests[key] || []).filter((t) => t > hourAgo);
    if (!requests[key].length) delete requests[key];
  }
}

function maskCode(code) {
  const c = codes.normalizeCode(code);
  const parts = c.split("-");
  if (parts.length >= 3) {
    parts[parts.length - 1] = "****";
    return parts.join("-");
  }
  return "USB-****-****";
}

function orderKey(row) {
  return row.paypalOrderId || row.code || "";
}

function listFromPurchases(email, existingKeys) {
  const purchases = loadPurchases();
  const allCodes = codes.load();
  const out = [];

  for (const [sessionId, row] of Object.entries(purchases)) {
    if (!row || !emailMatchesAny(email, row.email)) continue;

    const codeRow = allCodes[sessionId];
    if (codeRow) continue;

    const linkedOrderId = row.paypalOrderId || sessionId;
    const byOrder = codes.findByOrderId(linkedOrderId);
    if (byOrder) continue;

    const key = row.paypalOrderId || sessionId;
    if (existingKeys.has(key)) continue;

    const productIds = row.productIds || (row.productId ? [row.productId] : []);
    out.push({
      code: codes.isValidCodeFormat(sessionId) ? sessionId : null,
      productIds,
      purchasedAt: row.at || row.createdAt || null,
      redeemed: codeRow ? Boolean(codeRow.used) : false,
      redeemedAt: codeRow?.redeemedAt || null,
      isGift: false,
      role: "owner",
      paypalOrderId: row.paypalOrderId || (sessionId.startsWith("PAY") ? sessionId : null),
    });
    existingKeys.add(key);
  }

  return out;
}

function listOrdersForEmail(email) {
  const fromCodes = codes.listByEmail(email);
  const seen = new Set(fromCodes.map(orderKey).filter(Boolean));
  const fromPurchases = listFromPurchases(email, seen);
  const merged = [...fromCodes, ...fromPurchases];

  merged.sort((a, b) => {
    const ta = a.purchasedAt ? new Date(a.purchasedAt).getTime() : 0;
    const tb = b.purchasedAt ? new Date(b.purchasedAt).getTime() : 0;
    return tb - ta;
  });

  return merged;
}

function createAccessToken(email) {
  const em = normalizeEmail(email);
  const token = crypto.randomBytes(24).toString("hex");
  const store = loadStore();
  pruneSessions(store.sessions);
  const expiresAt = new Date();
  expiresAt.setHours(expiresAt.getHours() + TOKEN_HOURS);
  store.sessions[token] = { email: em, expiresAt: expiresAt.toISOString() };
  saveStore(store);
  return { token, expiresAt: expiresAt.toISOString() };
}

function validateToken(token) {
  if (!token) return null;
  const store = loadStore();
  pruneSessions(store.sessions);
  const row = store.sessions[token];
  if (!row) return null;
  if (new Date(row.expiresAt) < new Date()) {
    delete store.sessions[token];
    saveStore(store);
    return null;
  }
  return normalizeEmail(row.email);
}

function canRequestAccess(email) {
  const em = normalizeEmail(email);
  const store = loadStore();
  pruneRequests(store.requests);
  const times = store.requests[em] || [];
  const now = Date.now();
  if (times.length >= MAX_REQUESTS_PER_HOUR) {
    return {
      ok: false,
      error: "Too many sign-in emails sent. Wait an hour or contact support.",
    };
  }
  const last = times[times.length - 1];
  if (last && now - last < REQUEST_COOLDOWN_MS) {
    return { ok: false, error: "Please wait a minute before requesting another link." };
  }
  store.requests[em] = [...times, now];
  saveStore(store);
  return { ok: true };
}

function requestAccess(email, codeRaw) {
  if (!isValidEmail(email)) {
    return { ok: false, error: "Enter a valid email address." };
  }

  const owned = codeRaw ? codes.findOwnedCode(email, codeRaw) : null;
  if (codeRaw && !owned) {
    return {
      ok: false,
      error:
        "That code does not match this email. Use the email your code was sent to, or try your PayPal email.",
    };
  }

  const gate = canRequestAccess(email);
  if (!gate.ok) return gate;

  const sessionEmail = owned ? normalizeEmail(owned.row.email) : normalizeEmail(email);
  const { token, expiresAt } = createAccessToken(sessionEmail);
  return { ok: true, token, expiresAt, email: sessionEmail, verifiedWithCode: Boolean(owned) };
}

module.exports = {
  normalizeEmail,
  isValidEmail,
  maskCode,
  listOrdersForEmail,
  requestAccess,
  validateToken,
  TOKEN_HOURS,
};
