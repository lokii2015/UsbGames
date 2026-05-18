const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const DATA_DIR = path.join(__dirname, "data");
const FAQ_FILE = path.join(DATA_DIR, "faq-questions.json");
const ADMIN_SESSIONS_FILE = path.join(DATA_DIR, "faq-admin-sessions.json");

const ADMIN_SESSION_HOURS = 24;

function getAdminCode() {
  return String(process.env.FAQ_ADMIN_CODE || "").trim();
}

/** Curated answers — always shown under Common questions */
const COMMON_FAQ = [
  {
    id: "install",
    question: "How do I install games on my USB?",
    answer:
      "Download the launcher ZIP or individual game zips, unzip into UsbGames\\PortableGames\\ on your USB stick (keep each game’s folder name).",
  },
  {
    id: "payment",
    question: "How do I pay? What currency?",
    answer:
      "Checkout uses PayPal (balance, PayPal account, or card). Prices are in Canadian dollars (CAD). After payment, download links appear on the confirmation page.",
  },
  {
    id: "refund",
    question: "Can I get a refund?",
    answer:
      "See our Refund policy. Contact us with your PayPal receipt if something went wrong with your order.",
  },
  {
    id: "offline",
    question: "Do games need the internet?",
    answer:
      "No. After games are on your USB, play offline.",
  },
];

function ensureDataDir() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
}

function loadStore() {
  ensureDataDir();
  if (!fs.existsSync(FAQ_FILE)) return { questions: [] };
  try {
    const raw = JSON.parse(fs.readFileSync(FAQ_FILE, "utf8"));
    return { questions: Array.isArray(raw.questions) ? raw.questions : [] };
  } catch {
    return { questions: [] };
  }
}

function saveStore(data) {
  ensureDataDir();
  fs.writeFileSync(FAQ_FILE, JSON.stringify(data, null, 2));
}

function normalizeEmail(email) {
  return String(email || "")
    .trim()
    .toLowerCase();
}

function createId() {
  return crypto.randomBytes(8).toString("hex");
}

function submitQuestion({ email, name, question }) {
  const q = String(question || "").trim();
  if (q.length < 10) {
    return { ok: false, error: "Please write at least 10 characters in your question." };
  }
  if (q.length > 2000) {
    return { ok: false, error: "Question is too long (max 2000 characters)." };
  }

  const em = normalizeEmail(email);
  const store = loadStore();

  const recent = store.questions.filter((row) => {
    if (em && normalizeEmail(row.email) === em) {
      const age = Date.now() - new Date(row.createdAt).getTime();
      return age < 60 * 60 * 1000;
    }
    return false;
  });
  if (em && recent.length >= 5) {
    return { ok: false, error: "You’ve sent several questions recently. Try again in an hour." };
  }

  const row = {
    id: createId(),
    email: em || null,
    name: String(name || "").trim().slice(0, 80) || null,
    question: q,
    answer: null,
    status: "pending",
    createdAt: new Date().toISOString(),
  };
  store.questions.push(row);
  saveStore(store);
  return { ok: true, id: row.id };
}

function listCommunityAnswered() {
  const store = loadStore();
  return store.questions
    .filter((q) => q.status === "answered" && q.answer)
    .sort((a, b) => new Date(b.answeredAt || b.createdAt) - new Date(a.answeredAt || a.createdAt))
    .slice(0, 50)
    .map((q) => ({
      id: q.id,
      question: q.question,
      answer: q.answer,
      answeredAt: q.answeredAt || null,
    }));
}

function listForUser({ email }) {
  const store = loadStore();
  const em = normalizeEmail(email);
  if (!em) return [];
  return store.questions
    .filter((q) => normalizeEmail(q.email) === em)
    .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
    .map((q) => ({
      id: q.id,
      question: q.question,
      answer: q.answer,
      status: q.status,
      createdAt: q.createdAt,
      answeredAt: q.answeredAt || null,
    }));
}

function getPublicFaq() {
  return {
    common: COMMON_FAQ,
    community: listCommunityAnswered(),
  };
}

function loadAdminSessions() {
  ensureDataDir();
  if (!fs.existsSync(ADMIN_SESSIONS_FILE)) return { sessions: {} };
  try {
    const raw = JSON.parse(fs.readFileSync(ADMIN_SESSIONS_FILE, "utf8"));
    return { sessions: raw.sessions && typeof raw.sessions === "object" ? raw.sessions : {} };
  } catch {
    return { sessions: {} };
  }
}

function saveAdminSessions(data) {
  ensureDataDir();
  fs.writeFileSync(ADMIN_SESSIONS_FILE, JSON.stringify(data, null, 2));
}

function pruneAdminSessions(sessions) {
  const now = Date.now();
  for (const key of Object.keys(sessions)) {
    if (new Date(sessions[key].expiresAt).getTime() < now) {
      delete sessions[key];
    }
  }
}

function unlockAdmin(code) {
  const adminCode = getAdminCode();
  if (!adminCode || adminCode.length < 4) {
    return { ok: false, error: "FAQ admin is not configured. Add FAQ_ADMIN_CODE to checkout/.env and restart the server." };
  }
  if (String(code || "").trim() !== adminCode) {
    return { ok: false, error: "Wrong code. Check checkout/.env (not .env.example) and restart npm start." };
  }
  const token = crypto.randomBytes(24).toString("hex");
  const store = loadAdminSessions();
  pruneAdminSessions(store.sessions);
  const expiresAt = new Date();
  expiresAt.setHours(expiresAt.getHours() + ADMIN_SESSION_HOURS);
  store.sessions[token] = { expiresAt: expiresAt.toISOString() };
  saveAdminSessions(store);
  return { ok: true, token, expiresAt: expiresAt.toISOString() };
}

function isValidAdminToken(token) {
  if (!token) return false;
  const store = loadAdminSessions();
  pruneAdminSessions(store.sessions);
  const row = store.sessions[token];
  if (!row) return false;
  if (new Date(row.expiresAt) < new Date()) {
    delete store.sessions[token];
    saveAdminSessions(store);
    return false;
  }
  return true;
}

function listPendingQuestions() {
  const store = loadStore();
  return store.questions
    .filter((q) => q.status === "pending")
    .sort((a, b) => new Date(a.createdAt) - new Date(b.createdAt))
    .map((q) => ({
      id: q.id,
      question: q.question,
      email: q.email,
      name: q.name,
      createdAt: q.createdAt,
    }));
}

function answerQuestion(id, answerText) {
  const answer = String(answerText || "").trim();
  if (answer.length < 5) {
    return { ok: false, error: "Answer must be at least 5 characters." };
  }
  if (answer.length > 4000) {
    return { ok: false, error: "Answer is too long (max 4000 characters)." };
  }
  const store = loadStore();
  const row = store.questions.find((q) => q.id === id);
  if (!row) return { ok: false, error: "Question not found." };
  row.status = "answered";
  row.answer = answer;
  row.answeredAt = new Date().toISOString();
  saveStore(store);
  return { ok: true };
}

module.exports = {
  COMMON_FAQ,
  submitQuestion,
  getPublicFaq,
  listForUser,
  unlockAdmin,
  isValidAdminToken,
  listPendingQuestions,
  answerQuestion,
};
