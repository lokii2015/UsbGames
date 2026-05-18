/** Copy server FAQ file to site root faq-data.json for static HTML hosting */
const fs = require("fs");
const path = require("path");

const src = path.join(__dirname, "..", "data", "faq-questions.json");
const dest = path.join(__dirname, "..", "..", "faq-data.json");

if (!fs.existsSync(src)) {
  console.error("No", src, "— run the site and collect questions first.");
  process.exit(1);
}
fs.copyFileSync(src, dest);
console.log("Wrote", dest);
