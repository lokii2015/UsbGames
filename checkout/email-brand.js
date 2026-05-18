/**
 * Branded email wrapper — red header bar + logo (matches site header #cc0000).
 * Inbox avatar/circle still needs Gravatar or BIMI on your sending domain.
 */
const fs = require("fs");
const path = require("path");
const { publicSiteUrl } = require("./site-url");

const BRAND_RED = "#cc0000";
const LOGO_CID = "usbgames-logo";

const LOGO_PNG = path.join(__dirname, "..", "email-assets", "brand.png");

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function logoSrc(siteUrl, useCid) {
  if (useCid) return `cid:${LOGO_CID}`;
  return `${publicSiteUrl(siteUrl)}/email-assets/brand.png`;
}

function emailHeaderHtml(siteUrl, useCid) {
  const src = logoSrc(siteUrl, useCid);
  return (
    `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 24px;border-collapse:collapse">` +
    `<tr><td align="center" style="background:${BRAND_RED};padding:20px 24px">` +
    `<img src="${escapeHtml(src)}" alt="UsbGames" width="280" height="56" ` +
    `style="display:block;margin:0 auto;max-width:100%;height:auto;border:0" />` +
    `</td></tr></table>`
  );
}

function emailFooterHtml(siteUrl) {
  const site = escapeHtml(publicSiteUrl(siteUrl));
  return (
    `<p style="margin-top:28px;padding-top:16px;border-top:1px solid #e0e0e0;color:#888;font-size:0.8rem;text-align:center">` +
    `<a href="${site}" style="color:#888;text-decoration:none">${site}</a></p>`
  );
}

function wrapEmailBody(siteUrl, innerHtml, useCid) {
  return (
    `<!DOCTYPE html>` +
    `<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>` +
    `<body style="margin:0;padding:0;background:#f5f5f5">` +
    `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f5f5f5">` +
    `<tr><td align="center" style="padding:16px 12px">` +
    `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" ` +
    `style="max-width:560px;background:#ffffff;border-radius:8px;overflow:hidden">` +
    `<tr><td style="padding:0">` +
    emailHeaderHtml(siteUrl, useCid) +
    `<div style="padding:8px 28px 28px;font-family:Segoe UI,Helvetica,Arial,sans-serif;font-size:16px;line-height:1.55;color:#111">` +
    innerHtml +
    `</div>` +
    emailFooterHtml(siteUrl) +
    `</td></tr></table></td></tr></table></body></html>`
  );
}

function hasInlineLogo() {
  return fs.existsSync(LOGO_PNG);
}

function inlineLogoAttachment() {
  if (!hasInlineLogo()) return null;
  return {
    filename: "brand.png",
    content: fs.readFileSync(LOGO_PNG).toString("base64"),
    contentId: LOGO_CID,
  };
}

module.exports = {
  BRAND_RED,
  LOGO_CID,
  emailHeaderHtml,
  wrapEmailBody,
  hasInlineLogo,
  inlineLogoAttachment,
};
