#!/usr/bin/env node
/** Run: npm run test-email  (from checkout folder) */
require("dotenv").config({ path: require("path").join(__dirname, "..", ".env") });
const mail = require("../email");
const { SUPPORT_EMAIL } = require("../support");

const siteUrl = (process.env.SITE_URL || "http://localhost:4242").replace(/\/$/, "");
const to = process.argv[2] || SUPPORT_EMAIL;

(async () => {
  console.log("Sending test email to", to, "...");
  try {
    const result = await mail.sendTestEmail({ to, siteUrl });
    if (result.sent) {
      console.log("Done — check inbox (and spam) for:", to);
    } else {
      console.log("Not sent — set RESEND_API_KEY in checkout/.env and try again.");
      process.exit(1);
    }
  } catch (err) {
    console.error("Failed:", err.message);
    process.exit(1);
  }
})();
