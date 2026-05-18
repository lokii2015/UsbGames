const express = require("express");
const giftCards = require("./gift-cards");
const { resolveCart } = require("./products");

function getAdminCode() {
  return String(process.env.GIFT_CARD_ADMIN_CODE || process.env.FAQ_ADMIN_CODE || "").trim();
}

function createGiftCardRouter({ parseCartBody }) {
  const router = express.Router();

  router.post("/balance", (req, res) => {
    const code = req.body?.code;
    const result = giftCards.getBalance(code);
    if (!result.ok) return res.status(400).json({ error: result.error });
    res.json(result);
  });

  router.post("/quote", (req, res) => {
    const cart = parseCartBody(req.body);
    if (!cart) return res.status(400).json({ error: "Cart is empty or invalid." });
    const result = giftCards.quoteForCart(req.body?.code, cart.amount);
    if (!result.ok) return res.status(400).json({ error: result.error });
    res.json({
      ...result,
      cartTotalCents: cart.amount,
      cartTotalLabel: cart.priceLabel,
    });
  });

  router.post("/admin/link", (req, res) => {
    const adminCode = getAdminCode();
    if (!adminCode || String(req.body?.adminCode || "").trim() !== adminCode) {
      return res.status(403).json({ error: "Invalid admin code." });
    }
    const cards = req.body?.cards;
    if (!Array.isArray(cards) || !cards.length) {
      return res.status(400).json({ error: "Send cards: [{ code, amountDollars }, ...]" });
    }
    const result = giftCards.importCards(cards);
    if (!result.ok) return res.status(400).json({ error: result.error });
    res.json({
      ok: true,
      linked: result.linked,
      errors: result.errors,
      count: result.linked.length,
    });
  });

  router.post("/admin/create", (req, res) => {
    const adminCode = getAdminCode();
    if (!adminCode || String(req.body?.adminCode || "").trim() !== adminCode) {
      return res.status(403).json({ error: "Invalid admin code." });
    }
    const dollars = Number(req.body?.amountDollars ?? req.body?.amount);
    const amountCents = Math.round(dollars * 100);
    const result = giftCards.createCards({
      amountCents,
      count: req.body?.count || 1,
      note: req.body?.note,
    });
    if (!result.ok) return res.status(400).json({ error: result.error });
    res.json({
      ok: true,
      codes: result.codes,
      amountLabel: giftCards.formatMoney(result.amountCents),
      count: result.count,
    });
  });

  return router;
}

module.exports = { createGiftCardRouter };
