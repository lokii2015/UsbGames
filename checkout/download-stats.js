/**
 * Public download click counts: baseline (before tracking) + tracked (since launch).
 */
const fs = require("fs");
const path = require("path");

const DATA_DIR = path.join(__dirname, "data");
const STATS_PATH = path.join(DATA_DIR, "download-stats.json");
const DEFAULTS_PATH = path.join(__dirname, "download-stats.defaults.json");
/** Public copy for static pages (same origin, no API required). */
const PUBLIC_STATS_PATH = path.join(__dirname, "..", "download-stats.json");

function readJson(file, fallback) {
  try {
    if (fs.existsSync(file)) {
      return JSON.parse(fs.readFileSync(file, "utf8"));
    }
  } catch {
    /* ignore */
  }
  return fallback;
}

function writeJson(file, data) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(data, null, 2), "utf8");
}

function loadDefaults() {
  return readJson(DEFAULTS_PATH, { trackingStarted: new Date().toISOString(), items: {} });
}

function loadRuntime() {
  return readJson(STATS_PATH, { tracked: {} });
}

function saveRuntime(runtime) {
  writeJson(STATS_PATH, runtime);
}

function normalizeId(id) {
  return path.basename(String(id || "").trim());
}

function record(id) {
  const key = normalizeId(id);
  if (!key || !key.toLowerCase().endsWith(".zip")) return null;

  const defaults = loadDefaults();
  if (!defaults.items[key]) {
    defaults.items[key] = { label: key.replace(/\.zip$/i, ""), baseline: 0 };
  }

  const runtime = loadRuntime();
  runtime.tracked = runtime.tracked || {};
  runtime.tracked[key] = (Number(runtime.tracked[key]) || 0) + 1;
  saveRuntime(runtime);
  publishPublic();
  return getItem(key);
}

function publishPublic() {
  try {
    writeJson(PUBLIC_STATS_PATH, getPublic());
  } catch (err) {
    console.warn("download-stats publish:", err.message);
  }
}

function getItem(id) {
  const key = normalizeId(id);
  const defaults = loadDefaults();
  const runtime = loadRuntime();
  const meta = defaults.items[key] || { label: key.replace(/\.zip$/i, ""), baseline: 0 };
  const baseline = Math.max(0, Number(meta.baseline) || 0);
  const tracked = Math.max(0, Number(runtime.tracked?.[key]) || 0);
  return {
    id: key,
    label: meta.label || key,
    baseline,
    tracked,
    total: baseline + tracked,
    trackingStarted: defaults.trackingStarted || null,
  };
}

function getPublic() {
  const defaults = loadDefaults();
  const keys = new Set([
    ...Object.keys(defaults.items || {}),
    ...Object.keys(loadRuntime().tracked || {}),
  ]);
  const items = [...keys].sort().map((id) => getItem(id));
  return {
    trackingStarted: defaults.trackingStarted || null,
    items,
  };
}

function setBaseline(id, baseline) {
  const key = normalizeId(id);
  const defaults = loadDefaults();
  if (!defaults.items[key]) {
    defaults.items[key] = { label: key.replace(/\.zip$/i, ""), baseline: 0 };
  }
  defaults.items[key].baseline = Math.max(0, Number(baseline) || 0);
  writeJson(DEFAULTS_PATH, defaults);
  return getItem(key);
}

module.exports = {
  record,
  getItem,
  getPublic,
  setBaseline,
  publishPublic,
};
