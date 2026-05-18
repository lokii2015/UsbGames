/**
 * Send redemption codes — Resend SDK (same as resend.com docs) or Gmail SMTP.
 */
const nodemailer = require("nodemailer");
const { Resend } = require("resend");
const { SUPPORT_EMAIL, supportMessageText } = require("./support");

let resendClient = null;

function hasResend() {
  return Boolean(process.env.RESEND_API_KEY?.trim());
}

function hasSmtp() {
  return Boolean(process.env.SMTP_USER && process.env.SMTP_PASS);
}

function isConfigured() {
  return hasResend() || hasSmtp();
}

function getResend() {
  if (!resendClient) {
    resendClient = new Resend(process.env.RESEND_API_KEY.trim());
  }
  return resendClient;
}

function resendFrom() {
  const email = (process.env.RESEND_FROM_EMAIL || "onboarding@resend.dev")
    .replace(/^["']|["']$/g, "")
    .trim();
  const name = (process.env.RESEND_FROM_NAME || "UsbGames").replace(/^["']|["']$/g, "").trim();

  let raw = (process.env.RESEND_FROM || "").replace(/^["']|["']$/g, "").trim();
  // Unquoted "Name <addr>" in .env often breaks at the space — only "Name" is loaded
  if (raw && raw.includes("@")) {
    return raw;
  }
  if (name && email) {
    return `${name} <${email}>`;
  }
  return email;
}

function normalizeTo(email) {
  return String(email || "").trim().toLowerCase();
}

function transporter() {
  const host = process.env.SMTP_HOST || "smtp.gmail.com";
  const port = Number(process.env.SMTP_PORT) || 587;
  return nodemailer.createTransport({
    host,
    port,
    secure: port === 465,
    auth: {
      user: process.env.SMTP_USER,
      pass: process.env.SMTP_PASS,
    },
  });
}

function buildMessages({ code, productNames, redeemUrl, siteUrl }) {
  const games =
    productNames && productNames.length ? productNames.join(", ") : "your purchase";

  const html = `<!DOCTYPE html>
<html><body style="font-family:sans-serif;line-height:1.5;color:#111">
  <h2>Thanks for your UsbGames purchase</h2>
  <p>You bought: <strong>${escapeHtml(games)}</strong></p>
  <p>Your redemption code:</p>
  <p style="font-size:1.25rem;font-weight:bold;letter-spacing:0.05em">${escapeHtml(code)}</p>
  <p><a href="${escapeHtml(redeemUrl)}">Redeem your code</a> — use the same Gmail you entered at checkout.</p>
  <p style="color:#c00;font-size:0.9rem"><strong>This code expires in 48 hours.</strong> Redeem soon to download your games.</p>
  <p style="color:#666;font-size:0.9rem">Unzip downloads into <code>UsbGames\\PortableGames\\</code> on your USB.</p>
  <p style="color:#666;font-size:0.85rem">Didn&rsquo;t get this email within 48 hours? See <a href="${escapeHtml(siteUrl)}/refund.html">Refund Policy</a> and contact <a href="mailto:${escapeHtml(SUPPORT_EMAIL)}">${escapeHtml(SUPPORT_EMAIL)}</a>.</p>
  <p style="color:#666;font-size:0.85rem"><a href="${escapeHtml(siteUrl)}">${escapeHtml(siteUrl)}</a></p>
</body></html>`;

  const text = `Thanks for your UsbGames purchase (${games}).

Your code: ${code}

Redeem: ${redeemUrl}
Use the same Gmail you used at checkout.

This code expires in 48 hours.

${supportMessageText(siteUrl)}

— UsbGames`;

  return {
    subject: `UsbGames code: ${code}`,
    html,
    text,
  };
}

async function sendViaResend(to, messages) {
  const { data, error } = await getResend().emails.send({
    from: resendFrom(),
    to: normalizeTo(to),
    subject: messages.subject,
    html: messages.html,
    text: messages.text,
  });

  if (error) {
    throw new Error(error.message || JSON.stringify(error));
  }
  return { sent: true, provider: "resend", id: data?.id };
}

async function sendViaSmtp(to, messages) {
  const from =
    process.env.EMAIL_FROM || `UsbGames <${process.env.SMTP_USER || "noreply@usbgames.local"}>`;
  await transporter().sendMail({
    from,
    to,
    subject: messages.subject,
    text: messages.text,
    html: messages.html,
  });
  return { sent: true, provider: "smtp" };
}

async function sendRedeemCode({ to, code, productNames, redeemUrl, siteUrl }) {
  const messages = buildMessages({ code, productNames, redeemUrl, siteUrl });

  if (!isConfigured()) {
    console.log("\n📧 EMAIL NOT CONFIGURED — redemption code for", to);
    console.log("   Code:", code);
    console.log("   Redeem:", redeemUrl);
    console.log("   Set RESEND_API_KEY in checkout/.env\n");
    return { sent: false, logged: true };
  }

  if (hasResend()) {
    return sendViaResend(to, messages);
  }
  return sendViaSmtp(to, messages);
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Test email — example code only, not a real redeem code. */
async function sendTestEmail({ to, siteUrl }) {
  const exampleCode = "USB-XXXX-XXXX";
  const target = normalizeTo(to || SUPPORT_EMAIL);

  const html = `<p>UsbGames bot test — if you see this, email works.</p>
<p>Example code shape: <strong>${exampleCode}</strong> (not valid for redeem).</p>
<p>After a real purchase, redeem at ${escapeHtml(siteUrl || "your site")}/redeem.html</p>`;

  const text = `UsbGames bot test. Example code: ${exampleCode} (not valid). Redeem page: ${siteUrl}/redeem.html`;

  if (!isConfigured()) {
    console.log("\n📧 TEST — set RESEND_API_KEY in checkout/.env\n");
    return { sent: false, logged: true, to: target };
  }

  const messages = { subject: "UsbGames test email (bot OK)", html, text };
  if (hasResend()) {
    await sendViaResend(target, messages);
  } else {
    await sendViaSmtp(target, messages);
  }
  console.log("Test email sent to", target);
  return { sent: true, to: target };
}

module.exports = { isConfigured, hasResend, hasSmtp, sendRedeemCode, sendTestEmail };
