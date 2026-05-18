const express = require("express");
const faq = require("./faq");

function adminToken(req) {
  const h = req.headers["x-faq-admin"] || req.body?.token || req.query?.token;
  return typeof h === "string" ? h.trim() : null;
}

function requireAdmin(req, res, next) {
  const token = adminToken(req);
  if (!faq.isValidAdminToken(token)) {
    return res.status(401).json({ error: "Enter the staff code to answer FAQs." });
  }
  req.faqAdminToken = token;
  next();
}

function createFaqRouter() {
  const router = express.Router();

  router.get("/", (_req, res) => {
    res.json(faq.getPublicFaq());
  });

  router.post("/ask", (req, res) => {
    try {
      const { email, name, question } = req.body || {};
      const result = faq.submitQuestion({ email, name, question });
      if (!result.ok) return res.status(400).json({ error: result.error });
      res.json({ ok: true, id: result.id, message: "Thanks! We’ll review your question soon." });
    } catch (err) {
      console.error("FAQ ask error:", err);
      res.status(500).json({ error: "Could not send your question. Try again." });
    }
  });

  router.get("/mine", (req, res) => {
    const email = req.query?.email;
    if (!email) {
      return res.status(400).json({ error: "Enter your email to see your questions." });
    }
    const questions = faq.listForUser({ email });
    res.json({ questions });
  });

  router.post("/admin/unlock", (req, res) => {
    const result = faq.unlockAdmin(req.body?.code);
    if (!result.ok) return res.status(401).json({ error: result.error });
    res.json({ ok: true, token: result.token, expiresAt: result.expiresAt });
  });

  router.get("/admin/pending", requireAdmin, (_req, res) => {
    res.json({ questions: faq.listPendingQuestions() });
  });

  router.post("/admin/answer", requireAdmin, (req, res) => {
    const { id, answer } = req.body || {};
    if (!id) return res.status(400).json({ error: "Missing question id." });
    const result = faq.answerQuestion(id, answer);
    if (!result.ok) return res.status(400).json({ error: result.error });
    res.json({ ok: true, message: "Answer published on the FAQ page." });
  });

  return router;
}

module.exports = { createFaqRouter };
