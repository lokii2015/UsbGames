/**
 * Purchase history — email magic-link access (no accounts).
 */
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const codes = require("./codes");

const DATA_DIR = path.join(__dirname, "data");
const SESSIONS_FILE = path.join(DATA_DIR, "purchase-history-sessions.json");
const TOKEN_HOURS = 2;
const REQUEST_COOLDOWN_MS = 60 * 1000;
const MAX_REQUESTS_PER_HOUR = 5;

function ensureDir() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
}

function normalizeEmail(email) {
  return String(email || "")
    .trim()
    .toLowerCase();
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

function listOrdersForEmail(email) {
  return codes.listByEmail(email);
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

function requestAccess(email) {
  if (!isValidEmail(email)) {
    return { ok: false, error: "Enter a valid email address." };
  }
  const gate = canRequestAccess(email);
  if (!gate.ok) return gate;

  const { token, expiresAt } = createAccessToken(email);
  return { ok: true, token, expiresAt, email: normalizeEmail(email) };
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
