/**
 * PayPal webhook listener — verifies signature, fulfills orders (sends codes).
 */
const paypal = require("./paypal");
const bot = require("./paypal-bot");

const HANDLED = new Set([
  "CHECKOUT.ORDER.APPROVED",
  "PAYMENT.CAPTURE.COMPLETED",
  "CHECKOUT.ORDER.COMPLETED",
]);

async function verifyWebhook(headers, body) {
  const webhookId = process.env.PAYPAL_WEBHOOK_ID;
  if (!webhookId || !paypal.isConfigured()) return false;

  const token = await paypal.getAccessToken();
  const res = await fetch(`${paypal.apiBase()}/v1/notifications/verify-webhook-signature`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      auth_algo: headers["paypal-auth-algo"],
      cert_url: headers["paypal-cert-url"],
      transmission_id: headers["paypal-transmission-id"],
      transmission_sig: headers["paypal-transmission-sig"],
      transmission_time: headers["paypal-transmission-time"],
      webhook_id: webhookId,
      webhook_event: body,
    }),
  });

  const data = await res.json();
  return data.verification_status === "SUCCESS";
}

function orderIdFromEvent(event) {
  const r = event.resource;
  if (!r) return null;
  if (event.resource_type === "checkout-order" && r.id) return r.id;
  if (r.supplementary_data?.related_ids?.order_id) {
    return r.supplementary_data.related_ids.order_id;
  }
  if (r.billing_agreement_id) return null;
  return r.id || null;
}

function createWebhookHandler({ siteUrl }) {
  return async function handlePayPalWebhook(req, res) {
    if (!paypal.isConfigured()) {
      return res.status(503).json({ error: "PayPal not configured" });
    }

    const event = req.body;
    if (!event || !event.event_type) {
      return res.status(400).json({ error: "Invalid webhook body" });
    }

    const webhookId = process.env.PAYPAL_WEBHOOK_ID;
    if (webhookId) {
      try {
        const ok = await verifyWebhook(req.headers, event);
        if (!ok) {
          console.warn("PayPal webhook signature failed:", event.event_type);
          return res.status(401).json({ error: "Webhook verification failed" });
        }
      } catch (err) {
        console.error("Webhook verify error:", err);
        return res.status(500).json({ error: "Verification error" });
      }
    } else {
      console.warn("PAYPAL_WEBHOOK_ID not set — accepting webhook without verification (dev only)");
    }

    if (!HANDLED.has(event.event_type)) {
      return res.json({ received: true, skipped: event.event_type });
    }

    const orderId = orderIdFromEvent(event);
    if (!orderId) {
      return res.json({ received: true, skipped: "no_order_id" });
    }

    try {
      const result = await bot.fulfillFromPayPalOrderId(orderId, siteUrl);
      console.log(
        `PayPal bot: ${event.event_type} order ${orderId} → code ${result.code} (${result.emailSent ? "emailed" : "log only"})`
      );
      res.json({ received: true, code: result.code, existing: result.existing });
    } catch (err) {
      if (String(err.message).includes("not paid")) {
        return res.json({ received: true, pending: true });
      }
      console.error("Webhook fulfill error:", err.message);
      res.status(500).json({ error: err.message });
    }
  };
}

module.exports = { createWebhookHandler, verifyWebhook };
