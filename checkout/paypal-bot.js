/**
 * PayPal payment bot — on paid order, create code and email customer.
 */
const codes = require("./codes");
const mail = require("./email");
const pending = require("./pending-orders");
const paypal = require("./paypal");
const { resolveCart } = require("./products");

function normalizeEmail(email) {
  const e = String(email || "").trim().toLowerCase();
  if (!e || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e)) return null;
  return e;
}

/**
 * @param {object} opts
 * @param {string} opts.orderId PayPal order ID
 * @param {string[]} opts.productIds
 * @param {string} opts.email Customer Gmail from checkout
 * @param {string} opts.siteUrl
 */
async function fulfillPaidOrder({
  orderId,
  productIds,
  email,
  siteUrl,
  isGift,
  buyerEmail,
  giftMessage,
}) {
  const cart = resolveCart(productIds);
  if (!cart) throw new Error("Invalid products in order");

  const normalizedEmail = normalizeEmail(email);
  if (!normalizedEmail) throw new Error("Valid checkout email required");

  const { code, existing } = codes.createForOrder({
    orderId,
    productIds: cart.productIds,
    email: normalizedEmail,
  });

  const redeemUrl = `${siteUrl}/redeem.html`;
  const productNames = cart.items.map((p) => p.name);

  const mailResult = await mail.sendRedeemCode({
    to: normalizedEmail,
    code,
    productNames,
    redeemUrl,
    siteUrl,
    giftFromEmail: isGift ? normalizeEmail(buyerEmail) : null,
    giftMessage: isGift ? giftMessage : "",
  });

  return {
    code,
    email: normalizedEmail,
    buyerEmail: isGift ? normalizeEmail(buyerEmail) : null,
    isGift: Boolean(isGift),
    existing,
    emailSent: mailResult.sent,
    productNames,
    redeemUrl,
  };
}

async function fulfillFromPayPalOrderId(orderId, siteUrl) {
  const order = await paypal.ensureCaptured(orderId);
  if (!paypal.orderIsPaid(order)) {
    throw new Error("PayPal order is not paid");
  }

  const productIds = paypal.productIdsFromOrder(order);
  if (!productIds.length) throw new Error("No products on order");

  const pend = pending.get(orderId);
  const email = pend?.email || paypal.payerEmail(order);
  if (!email) throw new Error("No email for order — customer must enter Gmail at checkout");

  return fulfillPaidOrder({
    orderId,
    productIds,
    email,
    siteUrl,
    isGift: Boolean(pend?.isGift),
    buyerEmail: pend?.buyerEmail,
    giftMessage: pend?.giftMessage || "",
  });
}

module.exports = {
  normalizeEmail,
  fulfillPaidOrder,
  fulfillFromPayPalOrderId,
};
