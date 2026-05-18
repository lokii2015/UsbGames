/** Customer support contact (override in .env with SUPPORT_EMAIL) */
const SUPPORT_EMAIL = (
  process.env.SUPPORT_EMAIL || "EthanCiuffreda12@gmail.com"
).trim();

const SUPPORT_MAILTO = `mailto:${SUPPORT_EMAIL}`;

function supportMessageHtml(siteUrl) {
  const refund = `${siteUrl}/refund.html`;
  return (
    `If you did not receive your code within <strong>48 hours</strong> of payment, or your code expired, ` +
    `see our <a href="${refund}">Refund Policy</a> and email ` +
    `<a href="${SUPPORT_MAILTO}">${SUPPORT_EMAIL}</a> with your PayPal receipt.`
  );
}

function supportMessageText(siteUrl) {
  return (
    `If you did not receive your code within 48 hours of payment, or your code expired, ` +
    `see the Refund Policy (${siteUrl}/refund.html) and email ${SUPPORT_EMAIL} with your PayPal receipt.`
  );
}

module.exports = {
  SUPPORT_EMAIL,
  SUPPORT_MAILTO,
  supportMessageHtml,
  supportMessageText,
};
