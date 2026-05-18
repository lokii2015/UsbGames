/** Customer support contact (override in .env with SUPPORT_EMAIL) */
const SUPPORT_EMAIL = (
  process.env.SUPPORT_EMAIL || "EthanCiuffreda12@gmail.com"
).trim();

const SUPPORT_MAILTO = `mailto:${SUPPORT_EMAIL}`;

function redeemSupportHtml(siteUrl) {
  const support = `${escapeHtml(siteUrl)}/support.html`;
  const refund = `${escapeHtml(siteUrl)}/refund.html`;
  const mail = escapeHtml(SUPPORT_EMAIL);
  return (
    `<p style="margin-top:1.25rem;padding-top:1rem;border-top:1px solid #ddd;color:#444;font-size:0.9rem">` +
    `<strong>Code already used or having trouble redeeming?</strong><br>` +
    `Email <a href="mailto:${mail}">${mail}</a> and include:` +
    `<ul style="margin:0.5rem 0 0 1.1rem;padding:0">` +
    `<li>A photo or screenshot of your <strong>PayPal payment receipt</strong> (or checkout confirmation)</li>` +
    `<li>A screenshot of the <strong>error message</strong> when you try to redeem on our site</li>` +
    `</ul>` +
    `This helps us confirm the purchase is yours. The same applies if someone else got into your email and used your code before you did.` +
    ` See <a href="${support}">Support</a> and our <a href="${refund}">Refund Policy</a>.` +
    `</p>`
  );
}

function redeemSupportText(siteUrl) {
  return (
    `Code already used or having trouble redeeming?\n` +
    `Email ${SUPPORT_EMAIL} with:\n` +
    `- A photo/screenshot of your PayPal payment receipt (or checkout confirmation)\n` +
    `- A screenshot of the error when you try to redeem on our site\n` +
    `This helps us confirm the purchase is yours. Same if someone used your email and took your code before you.\n` +
    `Support: ${siteUrl}/support.html\n` +
    `Refund Policy: ${siteUrl}/refund.html`
  );
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** @deprecated use redeemSupportHtml */
function supportMessageHtml(siteUrl) {
  return redeemSupportHtml(siteUrl);
}

/** @deprecated use redeemSupportText */
function supportMessageText(siteUrl) {
  return redeemSupportText(siteUrl);
}

module.exports = {
  SUPPORT_EMAIL,
  SUPPORT_MAILTO,
  redeemSupportHtml,
  redeemSupportText,
  supportMessageHtml,
  supportMessageText,
};
