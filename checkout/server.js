const path = require("path");
require("dotenv").config({ path: path.join(__dirname, ".env") });
const crypto = require("crypto");
const fs = require("fs");
const express = require("express");
const Stripe = require("stripe");
const {
  getProduct,
  listProducts,
  resolveCart,
  formatPriceLabel,
  STORE_CURRENCY,
} = require("./products");
const paypal = require("./paypal");
const { createFaqRouter } = require("./faq-routes");
const { createPurchaseRouter } = require("./purchase-routes");
const codes = require("./codes");
const pending = require("./pending-orders");
const bot = require("./paypal-bot");
const mail = require("./email");
const { createWebhookHandler } = require("./paypal-webhook");
const { SUPPORT_EMAIL } = require("./support");
const { getSiteUrl, publicSiteUrl, CANONICAL_SITE_URL } = require("./site-url");

const PORT = Number(process.env.PORT) || 4242;
const SITE_URL = getSiteUrl(PORT);
const WEB_ROOT = path.join(__dirname, "..");
const PREMIUM_DIR = path.join(__dirname, "downloads");
const DATA_DIR = path.join(__dirname, "data");

const stripeKey = process.env.STRIPE_SECRET_KEY;
const signingSecret = process.env.DOWNLOAD_SIGNING_SECRET;
const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;

const stripe = stripeKey ? new Stripe(stripeKey) : null;

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

ensureDir(PREMIUM_DIR);
ensureDir(DATA_DIR);

const app = express();

app.use((req, res, next) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Faq-Admin");
  if (req.method === "OPTIONS") return res.sendStatus(204);
  next();
});

/** Stripe webhooks need raw body */
app.post(
  "/api/webhook",
  express.raw({ type: "application/json" }),
  async (req, res) => {
    if (!stripe || !webhookSecret) {
      return res.status(503).send("Webhook not configured");
    }
    const sig = req.headers["stripe-signature"];
    let event;
    try {
      event = stripe.webhooks.constructEvent(req.body, sig, webhookSecret);
    } catch (err) {
      console.error("Webhook signature failed:", err.message);
      return res.status(400).send(`Webhook Error: ${err.message}`);
    }

    if (event.type === "checkout.session.completed") {
      const session = event.data.object;
      const productId = session.metadata?.product_id;
      if (productId && session.payment_status === "paid") {
        recordPurchase(session.id, [productId], session.customer_details?.email, "stripe");
      }
    }
    res.json({ received: true });
  }
);

app.use(express.json());

app.use("/api/faq", createFaqRouter());

function buildDownloadResponse(sessionId, cart) {
  const downloads = cart.files.map((filename) => ({
    name: filename.replace(/\.zip$/i, ""),
    filename,
    url: `/api/download/${encodeURIComponent(
      filename
    )}?session_id=${encodeURIComponent(
      sessionId
    )}&sig=${signDownload(sessionId, filename)}`,
  }));

  return {
    product: { id: cart.productIds.join(","), name: cart.name },
    products: cart.items.map((p) => ({ id: p.id, name: p.name })),
    downloads,
  };
}

app.use(
  "/api/purchases",
  createPurchaseRouter({
    siteUrl: SITE_URL,
    buildDownloadResponse,
    sendAccessEmail: (opts) => mail.sendPurchaseHistoryLink(opts),
  })
);

app.get("/api/health", (_req, res) => {
  res.json({
    ok: true,
    paymentsEnabled: Boolean(stripe) || paypal.isConfigured(),
    stripe: Boolean(stripe),
    paypal: paypal.isConfigured(),
    paypalMe: paypal.PAYPAL_ME_USERNAME,
    emailBot: mail.isConfigured(),
    emailProvider: mail.activeProvider(),
    siteUrl: SITE_URL,
    supportEmail: SUPPORT_EMAIL,
  });
});

/** Send test email (example code USB-XXXX-XXXX, no real redeem). ?key=FAQ_ADMIN_CODE */
app.post("/api/test-email", async (req, res) => {
  const key = req.query.key || req.body?.key;
  if (!process.env.FAQ_ADMIN_CODE || key !== process.env.FAQ_ADMIN_CODE) {
    return res.status(403).json({ error: "Invalid or missing key" });
  }
  const to = req.body?.to || SUPPORT_EMAIL;
  try {
    const result = await mail.sendTestEmail({ to, siteUrl: SITE_URL });
    res.json({
      ok: true,
      sent: result.sent,
      to: result.to,
      message: result.sent
        ? `Test email sent to ${result.to}. Example code USB-XXXX-XXXX — not valid for redeem.`
        : "Email not configured — check server logs",
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

/** Public config for checkout page */
app.get("/api/config", (_req, res) => {
  const creds = paypal.credentials();
  res.json({
    siteUrl: SITE_URL,
    paypalClientId: creds?.clientId || null,
    paypalMeUsername: paypal.PAYPAL_ME_USERNAME,
    paypalConfigured: paypal.isConfigured(),
    stripeConfigured: Boolean(stripe),
    paypalMode: paypal.paypalMode(),
    paypalSdkHost: paypal.sdkBase(),
    supportEmail: SUPPORT_EMAIL,
  });
});

app.get("/api/products", (_req, res) => {
  res.json({
    products: listProducts().map((p) => ({
      id: p.id,
      name: p.name,
      description: p.description,
      amount: p.amount,
      priceLabel: formatPriceLabel(p),
    })),
  });
});

app.get("/api/product/:productId", (req, res) => {
  const product = getProduct(req.params.productId);
  if (!product) return res.status(404).json({ error: "Unknown product" });
  const cur = (product.currency || STORE_CURRENCY).toUpperCase();
  res.json({
    id: product.id,
    name: product.name,
    description: product.description,
    amount: product.amount,
    currency: product.currency || STORE_CURRENCY,
    priceLabel: formatPriceLabel(product),
    paypalMeUrl: paypal.paypalMeUrl(
      product.amount,
      `UsbGames: ${product.name}`,
      cur
    ),
  });
});

/** Prefer canonical SITE_URL; allow localhost origin for dev only. */
function resolveSiteUrl(body) {
  const raw = body?.siteUrl || body?.returnOrigin;
  if (raw && typeof raw === "string") {
    try {
      const u = new URL(raw.trim());
      if (u.protocol === "http:" || u.protocol === "https:") {
        const host = u.hostname.toLowerCase();
        if (host === "localhost" || host === "127.0.0.1") return u.origin;
      }
    } catch {
      /* ignore */
    }
  }
  return publicSiteUrl(null, SITE_URL);
}

function parseCheckoutEmails(body) {
  const isGift =
    body?.checkoutMode === "gift" || body?.gift === true || body?.isGift === true;
  if (isGift) {
    const recipientEmail = bot.normalizeEmail(body?.recipientEmail || body?.email);
    const buyerEmail = bot.normalizeEmail(body?.buyerEmail);
    const giftMessage = String(body?.giftMessage || "").trim().slice(0, 500);
    if (!recipientEmail) {
      return { error: "Enter the recipient email for this gift." };
    }
    if (!buyerEmail) {
      return { error: "Enter your email (you are paying for this gift)." };
    }
    if (recipientEmail === buyerEmail) {
      return { error: "Recipient email and your email must be different." };
    }
    return {
      isGift: true,
      email: recipientEmail,
      buyerEmail,
      giftMessage,
    };
  }
  const email = bot.normalizeEmail(body?.email);
  if (!email) return { error: "Enter your Gmail / email before paying." };
  return { isGift: false, email, buyerEmail: null, giftMessage: "" };
}

function parseCartBody(body) {
  const items = body?.items || body?.productIds;
  if (Array.isArray(items) && items.length > 0) {
    return resolveCart(items);
  }
  const single = body?.productId;
  if (single) return resolveCart([single]);
  return null;
}

/** Cart quote from product IDs */
app.post("/api/cart/quote", (req, res) => {
  const cart = parseCartBody(req.body);
  if (!cart) {
    return res.status(400).json({
      error: "Cart is empty or invalid",
      message: "Cart items must use the same currency.",
    });
  }
  const cur = cart.currency.toUpperCase();
  res.json({
    items: cart.items.map((p) => ({
      id: p.id,
      name: p.name,
      description: p.description,
      amount: p.amount,
      priceLabel: formatPriceLabel(p),
    })),
    totalCents: cart.amount,
    currency: cart.currency,
    totalLabel: cart.priceLabel,
    paypalMeUrl: paypal.paypalMeUrl(cart.amount, `UsbGames: ${cart.description}`, cur),
  });
});

/** $0 cart — email code immediately (test flow) */
app.post("/api/checkout/free-order", async (req, res) => {
  if (!signingSecret) {
    return res.status(503).json({
      error: "DOWNLOAD_SIGNING_SECRET not set in checkout/.env",
    });
  }
  const cart = parseCartBody(req.body);
  if (!cart) return res.status(400).json({ error: "Cart is empty or invalid" });
  if (cart.amount !== 0) {
    return res.status(400).json({ error: "This checkout is only for $0.00 test orders." });
  }
  const email = bot.normalizeEmail(req.body?.email);
  if (!email) return res.status(400).json({ error: "Enter a valid Gmail / email address." });

  try {
    const orderId = `free_${crypto.randomBytes(16).toString("hex")}`;
    const result = await bot.fulfillPaidOrder({
      orderId,
      productIds: cart.productIds,
      email,
      siteUrl: SITE_URL,
    });
    res.json({
      successUrl: `${SITE_URL}/order-complete.html?email=${encodeURIComponent(email)}`,
      code: result.code,
      emailSent: result.emailSent,
    });
  } catch (err) {
    res.status(500).json({ error: err.message || "Could not create code" });
  }
});

/** PayPal.me redirect URL for cart */
app.post("/api/paypal/me-url", (req, res) => {
  const cart = parseCartBody(req.body);
  if (!cart) return res.status(400).json({ error: "Cart is empty or invalid" });
  res.json({
    url: paypal.paypalMeUrl(
      cart.amount,
      `UsbGames: ${cart.description}`,
      cart.currency.toUpperCase()
    ),
    username: paypal.PAYPAL_ME_USERNAME,
    amount: (cart.amount / 100).toFixed(2),
    currency: cart.currency,
  });
});

/** Create PayPal order for embedded buttons */
app.post("/api/paypal/create-order", async (req, res) => {
  if (!paypal.isConfigured()) {
    return res.status(503).json({
      error: "PayPal API not configured",
      message: "Add PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET to checkout/.env",
    });
  }
  const cart = parseCartBody(req.body);
  if (!cart) return res.status(400).json({ error: "Cart is empty or invalid" });

  const checkout = parseCheckoutEmails(req.body);
  if (checkout.error) {
    return res.status(400).json({ error: checkout.error });
  }

  try {
    const siteUrl = resolveSiteUrl(req.body);
    const order = await paypal.createOrder(cart, siteUrl);
    pending.set(order.id, {
      email: checkout.email,
      productIds: cart.productIds,
      isGift: checkout.isGift,
      buyerEmail: checkout.buyerEmail,
      giftMessage: checkout.giftMessage,
    });
    res.json({
      orderId: order.id,
      approveUrl: paypal.approveUrlFromOrder(order),
    });
  } catch (err) {
    console.error("PayPal create order:", err);
    res.status(500).json({ error: err.message || "Could not create PayPal order" });
  }
});

/** Capture after buyer approves in PayPal popup */
app.post("/api/paypal/capture-order", async (req, res) => {
  if (!paypal.isConfigured()) {
    return res.status(503).json({ error: "PayPal not configured" });
  }
  const orderId = req.body?.orderId;
  if (!orderId) return res.status(400).json({ error: "Missing orderId" });

  try {
    const captured = await paypal.captureOrder(orderId);
    const productIds = paypal.productIdsFromOrder(captured);
    let botResult = null;
    if (productIds.length && paypal.orderIsPaid(captured)) {
      botResult = await bot.fulfillFromPayPalOrderId(orderId, SITE_URL);
    }
    const pend = pending.get(orderId);
    const recipientEmail =
      botResult?.email || pend?.email || paypal.payerEmail(captured);
    const completeEmail =
      botResult?.isGift && botResult?.buyerEmail
        ? botResult.buyerEmail
        : recipientEmail;
    let completeUrl = completeEmail
      ? `${SITE_URL}/order-complete.html?email=${encodeURIComponent(completeEmail)}`
      : `${SITE_URL}/order-complete.html`;
    if (botResult?.isGift && recipientEmail) {
      completeUrl +=
        "&gift=1&recipient=" + encodeURIComponent(recipientEmail);
    }
    res.json({
      orderId: captured.id,
      status: captured.status,
      productIds,
      code: botResult?.code || null,
      emailSent: botResult?.emailSent || false,
      isGift: Boolean(botResult?.isGift),
      recipientEmail: botResult?.isGift ? recipientEmail : null,
      completeUrl,
    });
  } catch (err) {
    console.error("PayPal capture:", err);
    res.status(500).json({ error: err.message || "Capture failed" });
  }
});

/** PayPal webhook — bot sends redemption code by email */
app.post("/api/paypal/webhook", createWebhookHandler({ siteUrl: SITE_URL }));

/** After PayPal redirect — ensure code was emailed */
app.post("/api/paypal/ensure-fulfillment", async (req, res) => {
  const orderId = req.body?.orderId;
  if (!orderId) return res.status(400).json({ error: "Missing orderId" });
  if (!paypal.isConfigured()) {
    return res.status(503).json({ error: "PayPal not configured" });
  }
  try {
    const result = await bot.fulfillFromPayPalOrderId(orderId, SITE_URL);
    res.json({
      ok: true,
      code: result.code,
      email: result.email,
      emailSent: result.emailSent,
    });
  } catch (err) {
    res.status(400).json({ ok: false, error: err.message });
  }
});

/** Redeem code from email */
app.post("/api/redeem", (req, res) => {
  if (!signingSecret) {
    return res.status(503).json({ error: "DOWNLOAD_SIGNING_SECRET not set" });
  }
  const codeRaw = req.body?.code;
  const email = req.body?.email;
  const result = codes.redeem(codeRaw, email);
  if (!result.ok) {
    return res.status(400).json({
      error: result.error,
      expired: Boolean(result.expired),
      supportEmail: SUPPORT_EMAIL,
      refundUrl: `${SITE_URL}/refund.html`,
    });
  }

  const cart = resolveCart(result.productIds);
  if (!cart) return res.status(400).json({ error: "Invalid products on code" });

  recordPurchase(result.code, cart.productIds, result.email, "redeem");
  res.json(buildDownloadResponse(result.code, cart));
});

app.post("/api/create-checkout-session", async (req, res) => {
  if (!stripe) {
    return res.status(503).json({
      error: "Stripe not configured",
      message: "Use PayPal on the checkout page, or add STRIPE_SECRET_KEY to checkout/.env",
    });
  }

  const productId = req.body?.productId;
  const product = getProduct(productId);
  if (!product) {
    return res.status(400).json({ error: "Unknown product" });
  }

  try {
    const session = await stripe.checkout.sessions.create({
      mode: "payment",
      payment_method_types: ["card"],
      line_items: [
        {
          price_data: {
            currency: product.currency || STORE_CURRENCY,
            unit_amount: product.amount,
            product_data: {
              name: product.name,
              description: product.description,
            },
          },
          quantity: 1,
        },
      ],
      metadata: { product_id: product.id },
      success_url: `${SITE_URL}/success.html?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${SITE_URL}/cancel.html`,
    });
    res.json({ url: session.url });
  } catch (err) {
    console.error("Checkout session error:", err);
    res.status(500).json({ error: err.message || "Checkout failed" });
  }
});

function recordPurchase(sessionId, productIds, email, provider = "paypal") {
  const ids = Array.isArray(productIds) ? productIds : [productIds].filter(Boolean);
  const file = path.join(DATA_DIR, "purchases.json");
  let purchases = {};
  if (fs.existsSync(file)) {
    try {
      purchases = JSON.parse(fs.readFileSync(file, "utf8"));
    } catch {
      purchases = {};
    }
  }
  purchases[sessionId] = {
    productIds: ids,
    productId: ids[0] || null,
    email: email || null,
    provider,
    at: new Date().toISOString(),
  };
  fs.writeFileSync(file, JSON.stringify(purchases, null, 2));
}

function signDownload(sessionId, filename) {
  const payload = `${sessionId}:${filename}`;
  const sig = crypto
    .createHmac("sha256", signingSecret || "dev-insecure")
    .update(payload)
    .digest("hex");
  return sig;
}

function verifyDownload(sessionId, filename, sig) {
  if (!sig) return false;
  const expected = signDownload(sessionId, filename);
  try {
    return crypto.timingSafeEqual(
      Buffer.from(sig, "hex"),
      Buffer.from(expected, "hex")
    );
  } catch {
    return false;
  }
}

async function stripeSessionIsPaid(sessionId) {
  if (!stripe) return null;
  const session = await stripe.checkout.sessions.retrieve(sessionId);
  if (session.payment_status !== "paid") return null;
  const productId = session.metadata?.product_id;
  if (!productId) return null;
  recordPurchase(
    sessionId,
    [productId],
    session.customer_details?.email,
    "stripe"
  );
  return resolveCart([productId]);
}

async function paypalOrderIsPaid(orderId) {
  if (!paypal.isConfigured()) return null;
  const order = await paypal.ensureCaptured(orderId);
  if (!paypal.orderIsPaid(order)) return null;
  const productIds = paypal.productIdsFromOrder(order);
  if (!productIds.length) return null;
  recordPurchase(orderId, productIds, paypal.payerEmail(order), "paypal");
  return resolveCart(productIds);
}

app.get("/api/verify-session", async (req, res) => {
  const sessionId = req.query.session_id || req.query.token;
  if (!sessionId || typeof sessionId !== "string") {
    return res.status(400).json({ error: "Missing session_id or token" });
  }

  if (!signingSecret) {
    return res.status(503).json({
      error: "DOWNLOAD_SIGNING_SECRET not set in checkout/.env",
    });
  }

  try {
    let cart = getCartFromSession(sessionId);

    if (!cart && sessionId.startsWith("cs_") && stripe) {
      cart = await stripeSessionIsPaid(sessionId);
    }

    if (!cart && paypal.isConfigured()) {
      cart = await paypalOrderIsPaid(sessionId);
    }

    if (!cart) {
      return res.status(402).json({
        error: "Payment not completed",
        message:
          "This payment is not confirmed yet. If you paid via PayPal.me, email your receipt for manual delivery.",
      });
    }

    res.json(buildDownloadResponse(sessionId, cart));
  } catch (err) {
    console.error("Verify session error:", err);
    res.status(500).json({ error: "Could not verify purchase" });
  }
});

app.get("/api/download/:filename", async (req, res) => {
  const sessionId = req.query.session_id;
  const sig = req.query.sig;
  const filename = path.basename(req.params.filename);

  if (!sessionId || !verifyDownload(sessionId, filename, sig)) {
    return res.status(403).send("Invalid or expired download link");
  }

  let cart = getCartFromSession(sessionId);
  if (!cart && sessionId.startsWith("cs_") && stripe) {
    cart = await stripeSessionIsPaid(sessionId);
  }
  if (!cart && paypal.isConfigured()) {
    cart = await paypalOrderIsPaid(sessionId);
  }
  if (!cart || !cart.files.includes(filename)) {
    return res.status(403).send("File not included in this purchase");
  }

  const filePath = path.join(PREMIUM_DIR, filename);
  if (!fs.existsSync(filePath)) {
    return res.status(404).send("File not found on server");
  }

  res.download(filePath, filename);
});

function getCartFromSession(sessionId) {
  const file = path.join(DATA_DIR, "purchases.json");
  if (fs.existsSync(file)) {
    try {
      const purchases = JSON.parse(fs.readFileSync(file, "utf8"));
      const row = purchases[sessionId];
      if (row) {
        const ids = row.productIds || (row.productId ? [row.productId] : []);
        return resolveCart(ids);
      }
    } catch {
      /* fall through */
    }
  }

  const all = codes.load();
  const row = all[sessionId];
  if (row && row.used) {
    return resolveCart(row.productIds);
  }
  return null;
}

const PREMIUM_ZIPS = new Set([
  "SnakeDeluxe.zip",
  "PixelFlapTurbo.zip",
  "TicTacToeAIPlus.zip",
  "GridDefense.zip",
  "PixelKart.zip",
  "PocketRPG.zip",
  "BlockStackDX.zip",
  "PixelChomp.zip",
  "BlackJack.zip",
  "UsbGames-StarterPack.zip",
  "UsbGames-RetroArcadePack.zip",
]);

app.get("/downloads/:file", (req, res, next) => {
  if (PREMIUM_ZIPS.has(req.params.file)) {
    return res.status(403).type("html").send(`<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Purchase required</title>
<link rel="stylesheet" href="/styles.css"></head>
<body><main class="container" style="padding:3rem 1.5rem">
<h1>Purchase required</h1>
<p>This game is sold in the <a href="/store.html">Store</a>. <a href="/checkout.html">Checkout</a> with PayPal or card.</p>
</main></body></html>`);
  }
  next();
});

app.use(express.static(WEB_ROOT));

app.listen(PORT, () => {
  console.log(`UsbGames checkout: ${SITE_URL}`);
  if (
    process.env.SITE_URL &&
    String(process.env.SITE_URL).toLowerCase().includes("netlify")
  ) {
    console.warn(
      `⚠ SITE_URL in env points to Netlify — emails/links use ${CANONICAL_SITE_URL} instead. Update Render env SITE_URL.`
    );
  }
  console.log(`Open FAQ: ${SITE_URL}/faq.html`);
  if (process.env.FAQ_ADMIN_CODE) {
    console.log("FAQ admin code: loaded from checkout/.env");
  } else {
    console.warn("FAQ admin code: missing — set FAQ_ADMIN_CODE in checkout/.env");
  }
  console.log(`PayPal.me: https://paypal.me/${paypal.PAYPAL_ME_USERNAME}`);
  console.log(
    `PayPal API: ${paypal.paypalMode().toUpperCase()} → ${paypal.apiBase()}`
  );
  if (!paypal.isConfigured()) {
    console.warn(
      "⚠ PayPal API keys missing — checkout uses paypal.me links only (manual fulfillment)"
    );
    console.warn("   Add PAYPAL_CLIENT_ID + PAYPAL_CLIENT_SECRET for auto-downloads");
  }
  if (!signingSecret) {
    console.warn("⚠ DOWNLOAD_SIGNING_SECRET missing — downloads will not work");
  }
  if (!mail.isConfigured()) {
    console.warn("⚠ Email not set — codes print to server logs instead of inbox");
    console.warn("   Free: RESEND_API_KEY (resend.com) or Gmail SMTP in checkout/.env");
  } else {
    const p = mail.activeProvider();
    if (p === "smtp") {
      console.log("📧 Email bot: Gmail SMTP — inbox avatar uses your Google account photo");
    } else if (p === "resend") {
      console.log("📧 Email bot: Resend (onboarding@resend.dev cannot use Gravatar)");
    }
  }
  if (paypal.isConfigured() && !process.env.PAYPAL_WEBHOOK_ID) {
    console.warn("⚠ PAYPAL_WEBHOOK_ID not set — webhook bot disabled (capture still sends codes)");
  }
  console.log(`Redeem codes: ${SITE_URL}/redeem.html`);
  console.log(`Purchase history: ${SITE_URL}/purchase-history.html`);
});
