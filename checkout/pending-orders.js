const fs = require("fs");
const path = require("path");

const FILE = path.join(__dirname, "data", "pending-orders.json");

function load() {
  const dir = path.dirname(FILE);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  if (!fs.existsSync(FILE)) return {};
  try {
    return JSON.parse(fs.readFileSync(FILE, "utf8"));
  } catch {
    return {};
  }
}

function save(data) {
  const dir = path.dirname(FILE);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(FILE, JSON.stringify(data, null, 2));
}

function set(orderId, { email, productIds }) {
  const all = load();
  all[orderId] = {
    email: String(email).trim().toLowerCase(),
    productIds: [...productIds],
    at: new Date().toISOString(),
  };
  save(all);
}

function get(orderId) {
  return load()[orderId] || null;
}

module.exports = { set, get };
