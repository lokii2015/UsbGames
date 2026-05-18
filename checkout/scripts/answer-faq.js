/**
 * Answer a pending FAQ question (run from checkout folder):
 *   node scripts/answer-faq.js <question-id> "Your answer text here"
 */
const fs = require("fs");
const path = require("path");

const FAQ_FILE = path.join(__dirname, "..", "data", "faq-questions.json");
const id = process.argv[2];
const answer = process.argv.slice(3).join(" ").trim();

if (!id || !answer) {
  console.error("Usage: node scripts/answer-faq.js <id> \"Answer text\"");
  process.exit(1);
}

const store = JSON.parse(fs.readFileSync(FAQ_FILE, "utf8"));
const row = store.questions.find((q) => q.id === id);
if (!row) {
  console.error("Question not found:", id);
  console.log("Pending:");
  store.questions
    .filter((q) => q.status === "pending")
    .forEach((q) => console.log(" ", q.id, "-", q.question.slice(0, 60)));
  process.exit(1);
}

row.status = "answered";
row.answer = answer;
row.answeredAt = new Date().toISOString();
fs.writeFileSync(FAQ_FILE, JSON.stringify(store, null, 2));
console.log("Answered:", row.question);
