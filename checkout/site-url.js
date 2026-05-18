/**
 * Public site URL for emails, PayPal return URLs, and links.
 * Always uses Render in production — never Netlify.
 */
const CANONICAL_SITE_URL = "https://usbgames.onrender.com";

function normalizeOrigin(raw) {
  const s = String(raw || "")
    .trim()
    .replace(/\/$/, "");
  if (!s) return null;
  try {
    const u = new URL(s.includes("://") ? s : `https://${s}`);
    if (u.protocol !== "http:" && u.protocol !== "https:") return null;
    return u.origin;
  } catch {
    return null;
  }
}

function isLocalOrigin(origin) {
  if (!origin) return false;
  try {
    const host = new URL(origin).hostname.toLowerCase();
    return host === "localhost" || host === "127.0.0.1";
  } catch {
    return false;
  }
}

function isNetlifyOrigin(origin) {
  if (!origin) return false;
  try {
    return new URL(origin).hostname.toLowerCase().endsWith(".netlify.app");
  } catch {
    return false;
  }
}

/** Site URL from env, with Netlify → Render and sensible production default. */
function getSiteUrl(port) {
  const fromEnv = normalizeOrigin(process.env.SITE_URL);
  if (fromEnv && isNetlifyOrigin(fromEnv)) return CANONICAL_SITE_URL;
  if (fromEnv) return fromEnv;

  if (process.env.RENDER || process.env.NODE_ENV === "production") {
    return CANONICAL_SITE_URL;
  }

  return `http://localhost:${port || 4242}`;
}

/** Normalize any URL passed from checkout (emails, PayPal). */
function publicSiteUrl(maybeUrl, fallback) {
  const base = normalizeOrigin(maybeUrl) || normalizeOrigin(fallback) || CANONICAL_SITE_URL;
  if (isNetlifyOrigin(base)) return CANONICAL_SITE_URL;
  if (isLocalOrigin(base)) return base;
  return base;
}

module.exports = {
  CANONICAL_SITE_URL,
  getSiteUrl,
  publicSiteUrl,
  isNetlifyOrigin,
};
