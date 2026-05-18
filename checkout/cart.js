/**
 * Shopping cart — localStorage, works on static pages and checkout server.
 */
(function (root) {
  const STORAGE_KEY = "usbgames_cart_v1";
  const listeners = new Set();

  function readRaw() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return [];
      const data = JSON.parse(raw);
      return Array.isArray(data) ? data : [];
    } catch {
      return [];
    }
  }

  function writeRaw(ids) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
    listeners.forEach((fn) => fn());
  }

  function normalizeId(id) {
    return String(id || "").trim();
  }

  function getIds() {
    return readRaw().filter((id) => root.UsbGamesCatalog?.getProduct(id));
  }

  function getLines() {
    return getIds()
      .map((id) => root.UsbGamesCatalog.getProduct(id))
      .filter(Boolean);
  }

  function count() {
    return getIds().length;
  }

  function totalCents() {
    return getLines().reduce((sum, p) => sum + p.amount, 0);
  }

  function cartCurrency() {
    const lines = getLines();
    if (lines.length === 0) return null;
    return lines[0].currency || "cad";
  }

  function add(productId) {
    const id = normalizeId(productId);
    const product = root.UsbGamesCatalog?.getProduct(id);
    if (!product) return false;
    const cur = product.currency || "cad";
    const existing = cartCurrency();
    if (existing && existing !== cur) {
      alert("Clear your cart before adding items with a different currency.");
      return false;
    }
    const ids = getIds();
    if (ids.includes(id)) return true;
    ids.push(id);
    writeRaw(ids);
    return true;
  }

  function remove(productId) {
    const id = normalizeId(productId);
    writeRaw(getIds().filter((x) => x !== id));
  }

  function clear() {
    writeRaw([]);
  }

  function has(productId) {
    return getIds().includes(normalizeId(productId));
  }

  function onChange(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  }

  function syncFromUrl() {
    const params = new URLSearchParams(location.search);
    const add = params.get("add") || params.get("product");
    if (add && addProductIds(add.split(","))) {
      params.delete("add");
      params.delete("product");
      const qs = params.toString();
      const path = location.pathname;
      history.replaceState(null, "", qs ? path + "?" + qs : path);
    }
  }

  function addProductIds(ids) {
    let changed = false;
    ids.forEach((id) => {
      if (add(id.trim())) changed = true;
    });
    return changed;
  }

  root.UsbGamesCart = {
    getIds,
    getLines,
    count,
    totalCents,
    add,
    remove,
    clear,
    has,
    onChange,
    syncFromUrl,
    addProductIds,
  };
})(typeof window !== "undefined" ? window : globalThis);
