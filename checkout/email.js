/**
 * Send redemption codes — Resend SDK (same as resend.com docs) or Gmail SMTP.
 */
const nodemailer = require("nodemailer");
const { Resend } = require("resend");
const { SUPPORT_EMAIL, redeemSupportHtml, redeemSupportText } = require("./support");
const { publicSiteUrl } = require("./site-url");
const brand = require("./email-brand");
let resendClient = null;

function hasResend() {
  return Boolean(process.env.RESEND_API_KEY?.trim());
}

function hasSmtp() {
  return Boolean(process.env.SMTP_USER && process.env.SMTP_PASS);
}

function isConfigured() {
  return Boolean(activeProvider());
}

/** auto | resend | smtp — use smtp to send from your Gmail (Gravatar / Google profile photo). */
function activeProvider() {
  const pick = (process.env.EMAIL_PROVIDER || "auto").trim().toLowerCase();
  if (pick === "smtp") return hasSmtp() ? "smtp" : null;
  if (pick === "resend") return hasResend() ? "resend" : null;
  if (hasResend()) return "resend";
  if (hasSmtp()) return "smtp";
  return null;
}

async function sendEmail(to, messages) {
  const provider = activeProvider();
  if (provider === "smtp") return sendViaSmtp(to, messages);
  if (provider === "resend") return sendViaResend(to, messages);
  throw new Error("Email not configured");
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

function finalizeEmail(siteUrl, innerHtml, subject, text) {
  const attachments = brand.hasInlineLogo()
    ? [brand.inlineLogoAttachment(siteUrl)].filter(Boolean)
    : [];
  return {
    subject,
    html: brand.wrapEmailBody(siteUrl, innerHtml),
    text,
    attachments,
  };
}

function buildMessages({ code, productNames, redeemUrl, siteUrl }) {
  const games =
    productNames && productNames.length ? productNames.join(", ") : "your purchase";

  const inner =
    `<h2 style="margin:0 0 16px;font-size:1.35rem;color:#111">Thanks for your UsbGames purchase</h2>` +
    `<p>You bought: <strong>${escapeHtml(games)}</strong></p>` +
    `<p>Your redemption code:</p>` +
    `<p style="font-size:1.25rem;font-weight:bold;letter-spacing:0.05em;margin:12px 0">${escapeHtml(code)}</p>` +
    `<p><a href="${escapeHtml(redeemUrl)}" style="color:#cc0000;font-weight:600">Redeem your code</a> — use the same Gmail you entered at checkout.</p>` +
    `<p style="color:#666;font-size:0.9rem">Unzip downloads into <code>UsbGames\\PortableGames\\</code> on your USB.</p>` +
    redeemSupportHtml(siteUrl) +
    `<p style="color:#666;font-size:0.85rem;margin-top:1rem">Didn&rsquo;t get this email? Email <a href="mailto:${escapeHtml(SUPPORT_EMAIL)}">${escapeHtml(SUPPORT_EMAIL)}</a> with your PayPal receipt.</p>`;

  const text = `Thanks for your UsbGames purchase (${games}).

Your code: ${code}

Redeem: ${redeemUrl}
Use the same Gmail you used at checkout.

${redeemSupportText(siteUrl)}

— UsbGames`;

  return finalizeEmail(siteUrl, inner, `UsbGames code: ${code}`, text);
}

function buildGiftMessages({
  code,
  productNames,
  redeemUrl,
  siteUrl,
  fromEmail,
  giftMessage,
}) {
  const games =
    productNames && productNames.length ? productNames.join(", ") : "UsbGames";
  const from = escapeHtml(fromEmail);
  const msgBlock = giftMessage
    ? `<p style="background:#f4f8f7;border-left:4px solid #64e0d0;padding:0.75rem 1rem;margin:1rem 0">` +
      `<strong>Message from your gift giver:</strong><br>${escapeHtml(giftMessage)}</p>`
    : "";
  const msgText = giftMessage
    ? `\nMessage from your gift giver:\n${giftMessage}\n`
    : "";

  const inner =
    `<h2 style="margin:0 0 16px;font-size:1.35rem;color:#111">You received a UsbGames gift</h2>` +
    `<p><strong>${from}</strong> bought you: <strong>${escapeHtml(games)}</strong></p>` +
    msgBlock +
    `<p style="font-size:1.05rem">This is a gift from <strong>${from}</strong> — remember to say <strong>thank you</strong> to them.</p>` +
    `<p>Your redemption code:</p>` +
    `<p style="font-size:1.25rem;font-weight:bold;letter-spacing:0.05em;margin:12px 0">${escapeHtml(code)}</p>` +
    `<p style="color:#555;font-size:0.9rem">Gift codes start with <strong>USB-G</strong> (e.g. USB-GXXXX-XXXX).</p>` +
    `<p><a href="${escapeHtml(redeemUrl)}" style="color:#cc0000;font-weight:600">Redeem your gift</a> — use the <strong>same email this message was sent to</strong> (not ${from}&rsquo;s).</p>` +
    `<p style="color:#666;font-size:0.9rem">Unzip downloads into <code>UsbGames\\PortableGames\\</code> on your USB.</p>` +
    redeemSupportHtml(siteUrl);

  const text = `You received a UsbGames gift from ${fromEmail}.

They bought: ${games}
${msgText}
This is a gift from ${fromEmail} — remember to say thank you to them.

Your gift code: ${code}
(Gift codes start with USB-G, e.g. USB-GXXXX-XXXX.)

Redeem: ${redeemUrl}
Use the email address this message was sent to (not the giver's email).

${redeemSupportText(siteUrl)}

— UsbGames`;

  return finalizeEmail(
    siteUrl,
    inner,
    `UsbGames gift for you — code ${code}`,
    text
  );
}

async function sendViaResend(to, messages) {
  const payload = {
    from: resendFrom(),
    to: normalizeTo(to),
    subject: messages.subject,
    html: messages.html,
    text: messages.text,
  };
  if (messages.attachments?.length) {
    payload.attachments = messages.attachments.map((a) => {
      const att = {
        filename: a.filename,
        contentId: a.contentId,
      };
      if (a.path) att.path = a.path;
      if (a.content) att.content = a.content;
      if (a.contentType) att.contentType = a.contentType;
      return att;
    });
  }
  const { data, error } = await getResend().emails.send(payload);

  if (error) {
    throw new Error(error.message || JSON.stringify(error));
  }
  return { sent: true, provider: "resend", id: data?.id };
}

async function sendViaSmtp(to, messages) {
  const from =
    process.env.EMAIL_FROM || `UsbGames <${process.env.SMTP_USER || "noreply@usbgames.local"}>`;
  const mail = {
    from,
    to,
    subject: messages.subject,
    text: messages.text,
    html: messages.html,
  };
  if (messages.attachments?.length) {
    mail.attachments = messages.attachments.map((a) => ({
      filename: a.filename,
      content: Buffer.from(a.content, "base64"),
      cid: a.contentId,
    }));
  }
  await transporter().sendMail(mail);
  return { sent: true, provider: "smtp" };
}

async function sendRedeemCode({
  to,
  code,
  productNames,
  redeemUrl,
  siteUrl,
  giftFromEmail,
  giftMessage,
}) {
  const site = publicSiteUrl(siteUrl);
  const redeem = redeemUrl && !redeemUrl.includes("netlify.app")
    ? redeemUrl
    : `${site}/redeem.html`;
  const messages =
    giftFromEmail
      ? buildGiftMessages({
          code,
          productNames,
          redeemUrl: redeem,
          siteUrl: site,
          fromEmail: giftFromEmail,
          giftMessage: giftMessage || "",
        })
      : buildMessages({ code, productNames, redeemUrl: redeem, siteUrl: site });

  if (!isConfigured()) {
    console.log("\n📧 EMAIL NOT CONFIGURED — redemption code for", to);
    console.log("   Code:", code);
    console.log("   Redeem:", redeemUrl);
    console.log("   Set RESEND_API_KEY in checkout/.env\n");
    return { sent: false, logged: true };
  }

  return sendEmail(to, messages);
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
  const site = publicSiteUrl(siteUrl);
  const exampleCode = "USB-XXXX-XXXX";
  const target = normalizeTo(to || SUPPORT_EMAIL);

  const inner =
    `<p>UsbGames bot test — if you see this, email works.</p>` +
    `<p>Example code shape: <strong>${exampleCode}</strong> (not valid for redeem).</p>` +
    `<p>After a real purchase, redeem at <a href="${escapeHtml(site)}/redeem.html">${escapeHtml(site)}/redeem.html</a></p>`;

  const text = `UsbGames bot test. Example code: ${exampleCode} (not valid). Redeem page: ${site}/redeem.html`;

  if (!isConfigured()) {
    console.log("\n📧 TEST — set RESEND_API_KEY in checkout/.env\n");
    return { sent: false, logged: true, to: target };
  }

  const messages = finalizeEmail(
    site,
    inner,
    "UsbGames test email (bot OK)",
    text
  );
  await sendEmail(target, messages);
  console.log("Test email sent to", target);
  return { sent: true, to: target };
}

function buildPurchaseHistoryMessages({ historyUrl, siteUrl, expiresHours }) {
  const inner =
    `<h2 style="margin:0 0 16px;font-size:1.35rem;color:#111">Your UsbGames purchase history</h2>` +
    `<p>Tap the link below to view what you bought, redemption status, and download links for redeemed orders.</p>` +
    `<p><a href="${escapeHtml(historyUrl)}" style="color:#cc0000;font-weight:600">View purchase history</a></p>` +
    `<p style="color:#666;font-size:0.9rem">This link expires in about ${expiresHours} hours. If you didn&rsquo;t request it, you can ignore this email.</p>`;

  const text = `UsbGames purchase history

View your orders: ${historyUrl}

This link expires in about ${expiresHours} hours.

— UsbGames`;

  return finalizeEmail(
    siteUrl,
    inner,
    "UsbGames — your purchase history link",
    text
  );
}

async function sendPurchaseHistoryLink({ to, historyUrl, siteUrl, expiresHours }) {
  const site = publicSiteUrl(siteUrl);
  const history =
    historyUrl && !historyUrl.includes("netlify.app")
      ? historyUrl
      : `${site}/purchase-history.html`;
  const messages = buildPurchaseHistoryMessages({
    historyUrl: history,
    siteUrl: site,
    expiresHours: expiresHours || 2,
  });

  if (!isConfigured()) {
    console.log("\n📧 EMAIL NOT CONFIGURED — purchase history link for", to);
    console.log("   ", historyUrl, "\n");
    return { sent: false, logged: true };
  }

  return sendEmail(to, messages);
}

module.exports = {
  isConfigured,
  activeProvider,
  hasResend,
  hasSmtp,
  sendRedeemCode,
  sendPurchaseHistoryLink,
  sendTestEmail,
};

