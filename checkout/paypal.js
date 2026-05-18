/**
 * PayPal REST API helpers (Orders v2).
 * Funds settle to the PayPal account linked to PAYPAL_CLIENT_ID / secret.
 * Use the same account as paypal.me/EthanCiuffreda.
 */

const PAYPAL_ME_USERNAME = (
  process.env.PAYPAL_ME_USERNAME || "EthanCiuffreda"
).replace(/^@/, "");

function paypalMode() {
  const m = String(process.env.PAYPAL_MODE || "sandbox")
    .trim()
    .toLowerCase();
  return m === "live" ? "live" : "sandbox";
}

function apiBase() {
  return paypalMode() === "live"
    ? "https://api-m.paypal.com"
    : "https://api-m.sandbox.paypal.com";
}

function sdkBase() {
  return paypalMode() === "live"
    ? "https://www.paypal.com"
    : "https://www.sandbox.paypal.com";
}

function credentials() {
  const clientId = process.env.PAYPAL_CLIENT_ID?.trim();
  const secret = process.env.PAYPAL_CLIENT_SECRET?.trim();
  if (!clientId || !secret) return null;
  if (clientId.includes("your_paypal") || secret.includes("your_paypal")) return null;
  return { clientId, secret };
}

function isConfigured() {
  return Boolean(credentials());
}

let tokenCache = { token: null, expiresAt: 0 };

async function getAccessToken() {
  const creds = credentials();
  if (!creds) throw new Error("PayPal not configured");

  if (tokenCache.token && Date.now() < tokenCache.expiresAt - 60_000) {
    return tokenCache.token;
  }

  const auth = Buffer.from(`${creds.clientId}:${creds.secret}`).toString("base64");
  const res = await fetch(`${apiBase()}/v1/oauth2/token`, {
    method: "POST",
    headers: {
      Authorization: `Basic ${auth}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: "grant_type=client_credentials",
  });

  const data = await res.json();
  if (!res.ok) {
    const mode = process.env.PAYPAL_MODE === "live" ? "live" : "sandbox";
    const msg = data.error_description || data.error || "PayPal auth failed";
    throw new Error(
      `${msg} — Use Sandbox Client ID + Secret from the same app when PAYPAL_MODE=sandbox (or Live keys when live). No spaces in .env.`
    );
  }

  tokenCache = {
    token: data.access_token,
    expiresAt: Date.now() + (data.expires_in || 3600) * 1000,
  };
  return data.access_token;
}

function formatAmount(cents) {
  return (cents / 100).toFixed(2);
}

/** paypal.me link — PayPal checkout there accepts PayPal balance, bank, and cards */
function paypalMeUrl(amountCents, note, currency = "CAD") {
  const amount = formatAmount(amountCents);
  const cur = String(currency || "CAD").toUpperCase();
  let url = `https://paypal.me/${encodeURIComponent(PAYPAL_ME_USERNAME)}/${amount}${cur}`;
  if (note) {
    url += `?note=${encodeURIComponent(note)}`;
  }
  return url;
}

async function createOrder(cart, siteUrl) {
  const token = await getAccessToken();
  const value = formatAmount(cart.amount);
  const customId = cart.productIds.join(",").slice(0, 127);

  const res = await fetch(`${apiBase()}/v2/checkout/orders`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      intent: "CAPTURE",
      purchase_units: [
        {
          reference_id: customId.slice(0, 50),
          custom_id: customId,
          description: cart.description.slice(0, 127),
          amount: {
            currency_code: String(cart.currency || "cad").toUpperCase(),
            value,
          },
        },
      ],
      application_context: {
        brand_name: "UsbGames",
        shipping_preference: "NO_SHIPPING",
        user_action: "PAY_NOW",
        landing_page: "BILLING",
        return_url: `${siteUrl}/order-complete.html`,
        cancel_url: `${siteUrl}/cancel.html`,
      },
    }),
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(
      data.message || data.details?.[0]?.description || "PayPal create order failed"
    );
  }
  return data;
}

async function captureOrder(orderId) {
  const token = await getAccessToken();
  const res = await fetch(`${apiBase()}/v2/checkout/orders/${orderId}/capture`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(
      data.message || data.details?.[0]?.description || "PayPal capture failed"
    );
  }
  return data;
}

async function getOrder(orderId) {
  const token = await getAccessToken();
  const res = await fetch(`${apiBase()}/v2/checkout/orders/${orderId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.message || "PayPal get order failed");
  }
  return data;
}

function orderIsPaid(order) {
  const status = order.status;
  if (status === "COMPLETED") return true;
  const unit = order.purchase_units?.[0];
  const capture = unit?.payments?.captures?.[0];
  return capture?.status === "COMPLETED";
}

function productIdsFromOrder(order) {
  const unit = order.purchase_units?.[0];
  const raw = unit?.custom_id || unit?.reference_id || "";
  if (!raw) return [];
  return String(raw)
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function payerEmail(order) {
  return order.payer?.email_address || null;
}

function approveUrlFromOrder(order) {
  const link = order?.links?.find((l) => l.rel === "approve");
  return link?.href || null;
}

/** If buyer approved on PayPal's page but capture not done yet, capture now. */
async function ensureCaptured(orderId) {
  let order = await getOrder(orderId);
  if (order.status === "APPROVED") {
    order = await captureOrder(orderId);
  }
  return order;
}

module.exports = {
  isConfigured,
  credentials,
  paypalMode,
  apiBase,
  sdkBase,
  getAccessToken,
  paypalMeUrl,
  PAYPAL_ME_USERNAME,
  createOrder,
  captureOrder,
  getOrder,
  orderIsPaid,
  productIdsFromOrder,
  payerEmail,
  approveUrlFromOrder,
  ensureCaptured,
};
