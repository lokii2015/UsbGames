/** Match checkout, PayPal, and Gmail alias addresses (user vs user+tag@gmail.com). */

function normalizeEmail(email) {
  return String(email || "")
    .trim()
    .toLowerCase();
}

function gmailCanonical(email) {
  const em = normalizeEmail(email);
  const at = em.lastIndexOf("@");
  if (at < 1) return null;
  let local = em.slice(0, at);
  let domain = em.slice(at + 1);
  if (domain === "googlemail.com") domain = "gmail.com";
  if (domain !== "gmail.com") return null;
  local = local.split("+")[0].replace(/\./g, "");
  return `${local}@gmail.com`;
}

function emailsEquivalent(a, b) {
  const x = normalizeEmail(a);
  const y = normalizeEmail(b);
  if (!x || !y) return false;
  if (x === y) return true;
  const gx = gmailCanonical(x);
  const gy = gmailCanonical(y);
  return Boolean(gx && gy && gx === gy);
}

function collectEmails(...values) {
  const out = [];
  const seen = new Set();
  for (const v of values) {
    if (v == null) continue;
    const list = Array.isArray(v) ? v : [v];
    for (const item of list) {
      const n = normalizeEmail(item);
      if (!n || seen.has(n)) continue;
      seen.add(n);
      out.push(n);
    }
  }
  return out;
}

function rowLookupEmails(row, pendingRow) {
  const emails = collectEmails(
    row.email,
    row.buyerEmail,
    row.lookupEmails,
    pendingRow?.email,
    pendingRow?.buyerEmail
  );
  return emails;
}

function emailMatchesAny(searchEmail, candidates) {
  const list = collectEmails(candidates);
  return list.some((c) => emailsEquivalent(c, searchEmail));
}

module.exports = {
  normalizeEmail,
  gmailCanonical,
  emailsEquivalent,
  collectEmails,
  rowLookupEmails,
  emailMatchesAny,
};
