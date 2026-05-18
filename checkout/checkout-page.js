/**
 * Cart checkout — PayPal Smart Buttons (PayPal + card) and $0 test orders.
 */
(function () {
  const cart = window.UsbGamesCart;
  const catalog = window.UsbGamesCatalog;
  if (!cart || !catalog) return;

  const emptyEl = document.getElementById("cart-empty");
  const mainEl = document.getElementById("checkout-main");
  const linesEl = document.getElementById("cart-lines");
  const totalEl = document.getElementById("cart-total");
  const subtitle = document.getElementById("checkout-subtitle");
  const errorEl = document.getElementById("checkout-error");
  const loadingEl = document.getElementById("checkout-loading");
  const serverHint = document.getElementById("checkout-server-hint");
  const panelFree = document.getElementById("panel-free");
  const panelPaid = document.getElementById("panel-paid");

  let config = null;
  let paypalButtonsReady = false;

  function showError(msg) {
    errorEl.hidden = false;
    errorEl.textContent = msg;
  }

  function clearError() {
    errorEl.hidden = true;
    errorEl.textContent = "";
  }

  function getCheckoutEmail() {
    const el = document.getElementById("checkout-email");
    return el ? el.value.trim() : "";
  }

  function cartPayload() {
    return {
      items: cart.getIds(),
      email: getCheckoutEmail(),
      siteUrl: window.location.origin,
    };
  }

  function requireEmail() {
    const email = getCheckoutEmail();
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      showError("Enter your Gmail / email before paying.");
      document.getElementById("checkout-email")?.focus();
      return false;
    }
    return true;
  }

  function cartCurrencyCode() {
    const lines = cart.getLines();
    if (!lines.length) return "CAD";
    return (lines[0].currency || "cad").toUpperCase();
  }

  function applyPaymentPanels(isFree) {
    if (panelFree) panelFree.hidden = !isFree;
    if (panelPaid) panelPaid.hidden = isFree;
  }

  function renderCart() {
    const lines = cart.getLines();
    const total = cart.totalCents();
    const totalLabel = catalog.formatCartTotal(lines);

    if (lines.length === 0) {
      emptyEl.hidden = false;
      mainEl.hidden = true;
      subtitle.textContent = "Your cart is empty.";
      return;
    }

    emptyEl.hidden = true;
    mainEl.hidden = false;
    subtitle.textContent =
      lines.length === 1
        ? lines[0].name + " · " + totalLabel
        : lines.length + " items · " + totalLabel;

    totalEl.textContent = totalLabel;

    const isFree = total === 0;
    applyPaymentPanels(isFree);

    linesEl.innerHTML = "";
    lines.forEach((p) => {
      const li = document.createElement("li");
      li.className = "cart-line";
      li.innerHTML =
        '<div class="cart-line-info">' +
        '<span class="cart-line-name">' +
        escapeHtml(p.name) +
        "</span>" +
        '<span class="cart-line-price">' +
        p.priceLabel +
        "</span>" +
        "</div>" +
        '<button type="button" class="cart-line-remove" data-remove="' +
        p.id +
        '" aria-label="Remove ' +
        escapeHtml(p.name) +
        '">Remove</button>';
      linesEl.appendChild(li);
    });

    linesEl.querySelectorAll("[data-remove]").forEach((btn) => {
      btn.addEventListener("click", () => {
        cart.remove(btn.getAttribute("data-remove"));
        if (paypalButtonsReady) location.reload();
        else renderCart();
      });
    });

    if (!isFree && !paypalButtonsReady) initPayPalButtons();
  }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  document.getElementById("btn-free-checkout")?.addEventListener("click", async () => {
    if (!requireEmail()) return;
    clearError();
    loadingEl.hidden = false;
    const { ok, data } = await apiFetch("/api/checkout/free-order", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cartPayload()),
    });
    loadingEl.hidden = true;
    if (!ok) {
      showError(data.error || data.message || "Could not complete free order");
      return;
    }
    cart.clear();
    location.href =
      data.successUrl ||
      "/order-complete.html?email=" + encodeURIComponent(getCheckoutEmail());
  });

  document.getElementById("btn-clear-cart").addEventListener("click", () => {
    if (confirm("Remove all items from your cart?")) {
      cart.clear();
      renderCart();
    }
  });

  function apiUrl(path) {
    const base = typeof window.USBGAMES_API === "string" ? window.USBGAMES_API : "";
    return base + path;
  }

  async function apiFetch(url, options) {
    try {
      const res = await fetch(apiUrl(url), options);
      const data = await res.json().catch(() => ({}));
      return { ok: res.ok, data };
    } catch {
      return {
        ok: false,
        data: {
          error:
            "Checkout API unreachable. On Netlify: link /api to Render (netlify.toml) or set meta usbgames-api. See checkout/DEPLOY-NETLIFY.txt.",
        },
      };
    }
  }

  async function createPayPalOrder() {
    if (!requireEmail()) throw new Error("Enter your email before paying.");
    const { ok, data } = await apiFetch("/api/paypal/create-order", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cartPayload()),
    });
    if (!ok) throw new Error(data.error || data.message || "Could not start payment");
    return data;
  }

  async function afterPaymentSuccess(cap) {
    cart.clear();
    const email = encodeURIComponent(getCheckoutEmail());
    if (cap.completeUrl) {
      location.href = cap.completeUrl;
      return;
    }
    location.href = "/order-complete.html?email=" + email;
  }

  function loadPayPalSdk(clientId, currency) {
    return new Promise((resolve, reject) => {
      const isLive = config?.paypalMode === "live";
      const sdkHost =
        config?.paypalSdkHost ||
        (isLive ? "https://www.paypal.com" : "https://www.sandbox.paypal.com");

      document.querySelectorAll('script[src*="paypal.com/sdk/js"]').forEach((s) => s.remove());
      if (window.paypal) {
        try {
          delete window.paypal;
        } catch (_) {
          window.paypal = undefined;
        }
      }

      const cur = (currency || "CAD").toUpperCase();
      const script = document.createElement("script");
      script.src =
        sdkHost +
        "/sdk/js?client-id=" +
        encodeURIComponent(clientId) +
        "&currency=" +
        encodeURIComponent(cur) +
        "&intent=capture&components=buttons" +
        "&enable-funding=card,paypal" +
        "&disable-funding=paylater,venmo,credit" +
        (isLive ? "" : cur === "CAD" ? "&buyer-country=CA" : "&buyer-country=US");
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Could not load PayPal SDK"));
      document.body.appendChild(script);
    });
  }

  function buttonOptions() {
    return {
      style: { layout: "vertical", shape: "rect", label: "pay", color: "gold" },
      createOrder: async () => {
        const data = await createPayPalOrder();
        return data.orderId;
      },
      onApprove: async (data) => {
        clearError();
        loadingEl.hidden = false;
        const { ok, data: cap } = await apiFetch("/api/paypal/capture-order", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ orderId: data.orderID }),
        });
        loadingEl.hidden = true;
        if (!ok) throw new Error(cap.error || "Payment failed");
        await afterPaymentSuccess(cap);
      },
      onError: (err) => {
        console.error("PayPal error", err);
        showError("Payment could not be completed. Check your email is entered and try again.");
      },
      onCancel: () => {
        showError("Payment cancelled.");
      },
    };
  }

  async function renderPayPalButtons() {
    const container = document.getElementById("paypal-button-container");
    if (!container || !window.paypal) return;
    container.innerHTML = "";
    try {
      await window.paypal.Buttons(buttonOptions()).render("#paypal-button-container");
    } catch (err) {
      console.error(err);
      container.innerHTML =
        '<p class="checkout-panel-hint">PayPal buttons could not load. Restart the checkout server and refresh.</p>';
    }
  }

  async function initPayPalButtons() {
    if (cart.count() === 0) return;

    const { ok, data } = await apiFetch("/api/config");
    if (ok) config = data;

    if (!config?.paypalClientId) {
      serverHint.hidden = false;
      serverHint.textContent =
        "Checkout API not connected. Run npm start in checkout/ (localhost) or deploy API + Netlify proxy.";
      document.getElementById("paypal-button-container").innerHTML =
        '<p class="checkout-panel-hint">Start the checkout server to show payment buttons.</p>';
      return;
    }

    loadingEl.hidden = false;
    try {
      await loadPayPalSdk(config.paypalClientId, cartCurrencyCode());
      await renderPayPalButtons();
      paypalButtonsReady = true;
    } catch (err) {
      showError(err.message);
    } finally {
      loadingEl.hidden = true;
    }
  }

  const emailEl = document.getElementById("checkout-email");
  if (emailEl) {
    try {
      const saved = localStorage.getItem("usbgames_checkout_email");
      if (saved) emailEl.value = saved;
    } catch (_) {}
    emailEl.addEventListener("change", () => {
      try {
        localStorage.setItem("usbgames_checkout_email", emailEl.value.trim());
      } catch (_) {}
    });
  }

  cart.syncFromUrl();
  cart.onChange(renderCart);
  renderCart();
})();
