const express = require("express");
const history = require("./purchase-history");
const { resolveCart } = require("./products");

function createPurchaseRouter({ siteUrl, buildDownloadResponse, sendAccessEmail }) {
  const router = express.Router();

  router.post("/request-access", async (req, res) => {
    try {
      const email = req.body?.email;
      const result = history.requestAccess(email);
      if (!result.ok) return res.status(400).json({ error: result.error });

      const historyUrl = `${siteUrl}/purchase-history.html?token=${encodeURIComponent(
        result.token
      )}`;

      const mailResult = await sendAccessEmail({
        to: result.email,
        historyUrl,
        siteUrl,
        expiresHours: history.TOKEN_HOURS,
      });

      res.json({
        ok: true,
        message: mailResult.sent
          ? `We sent a sign-in link to ${result.email}. Check your inbox (and spam).`
          : `Email is not configured on the server — open this link now: ${historyUrl}`,
        emailSent: Boolean(mailResult.sent),
        expiresAt: result.expiresAt,
      });
    } catch (err) {
      console.error("Purchase history request error:", err);
      res.status(500).json({ error: "Could not send sign-in link. Try again." });
    }
  });

  router.get("/history", (req, res) => {
    const token = typeof req.query?.token === "string" ? req.query.token.trim() : "";
    const email = history.validateToken(token);
    if (!email) {
      return res.status(401).json({
        error: "This link is invalid or expired. Request a new one from Purchase history.",
      });
    }

    const rows = history.listOrdersForEmail(email);
    const orders = rows.map((row) => {
      const cart = resolveCart(row.productIds);
      const products = cart
        ? cart.items.map((p) => ({ id: p.id, name: p.name }))
        : row.productIds.map((id) => ({ id, name: id }));

      let downloads = [];
      if (row.redeemed && cart) {
        const payload = buildDownloadResponse(row.code, cart);
        downloads = payload.downloads || [];
      }

      return {
        codeMasked: history.maskCode(row.code),
        products,
        purchasedAt: row.purchasedAt,
        redeemed: row.redeemed,
        redeemedAt: row.redeemedAt,
        isGift: row.isGift,
        role: row.role,
        downloads,
        redeemUrl: `${siteUrl}/redeem.html?email=${encodeURIComponent(email)}`,
      };
    });

    res.json({ email, orders, expiresInHours: history.TOKEN_HOURS });
  });

  return router;
}

module.exports = { createPurchaseRouter };
