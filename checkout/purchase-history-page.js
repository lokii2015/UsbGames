(function () {
  const params = new URLSearchParams(location.search);
  const token = params.get("token");

  const requestSection = document.getElementById("history-request");
  const requestForm = document.getElementById("history-request-form");
  const emailInput = document.getElementById("history-email");
  const requestMsg = document.getElementById("history-request-msg");
  const requestErr = document.getElementById("history-request-error");
  const loadingEl = document.getElementById("history-loading");
  const errorEl = document.getElementById("history-error");
  const listEl = document.getElementById("history-list");
  const emptyEl = document.getElementById("history-empty");

  if (params.get("email")) emailInput.value = params.get("email");

  function apiUrl(path) {
    const base = typeof window.USBGAMES_API === "string" ? window.USBGAMES_API : "";
    return base + path;
  }

  function apiBase() {
    return typeof window.USBGAMES_API === "string" ? window.USBGAMES_API : "";
  }

  function formatDate(iso) {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      });
    } catch {
      return iso;
    }
  }

  function statusLabel(order) {
    if (order.redeemed) {
      return "Redeemed" + (order.redeemedAt ? " · " + formatDate(order.redeemedAt) : "");
    }
    return "Not redeemed yet";
  }

  function roleNote(order) {
    if (order.role === "buyer") return "Gift you sent";
    if (order.role === "recipient") return "Gift to you";
    return "";
  }

  function renderOrders(data) {
    requestSection.hidden = true;
    loadingEl.hidden = true;
    listEl.hidden = false;
    listEl.innerHTML = "";

    const intro = document.createElement("p");
    intro.className = "purchase-signed-in";
    intro.textContent = "Signed in as " + data.email + ". Link expires in about " + data.expiresInHours + " hours.";
    listEl.appendChild(intro);

    if (!data.orders || !data.orders.length) {
      emptyEl.hidden = false;
      return;
    }
    emptyEl.hidden = true;

    data.orders.forEach((order) => {
      const card = document.createElement("article");
      card.className = "card purchase-order-card";

      const names = (order.products || []).map((p) => p.name).join(", ") || "UsbGames purchase";
      const role = roleNote(order);

      card.innerHTML =
        '<h2 class="purchase-order-title">' +
        escapeHtml(names) +
        "</h2>" +
        (role ? '<p class="purchase-order-role">' + escapeHtml(role) + "</p>" : "") +
        '<dl class="purchase-order-meta">' +
        "<div><dt>Purchased</dt><dd>" +
        escapeHtml(formatDate(order.purchasedAt)) +
        "</dd></div>" +
        "<div><dt>Code</dt><dd><code>" +
        escapeHtml(order.codeMasked) +
        "</code></dd></div>" +
        "<div><dt>Status</dt><dd>" +
        escapeHtml(statusLabel(order)) +
        "</dd></div>" +
        "</dl>";

      const actions = document.createElement("div");
      actions.className = "purchase-order-actions";

      if (order.redeemed && order.downloads && order.downloads.length) {
        const dlTitle = document.createElement("p");
        dlTitle.className = "purchase-download-label";
        dlTitle.textContent = "Download access";
        actions.appendChild(dlTitle);
        const ul = document.createElement("ul");
        ul.className = "steps";
        order.downloads.forEach((d) => {
          const li = document.createElement("li");
          const a = document.createElement("a");
          a.className = "button";
          a.href = apiBase() + d.url;
          a.download = d.filename;
          a.textContent = "Download " + d.name;
          li.appendChild(a);
          ul.appendChild(li);
        });
        actions.appendChild(ul);
      } else {
        const a = document.createElement("a");
        a.className = "button button--secondary";
        a.href = order.redeemUrl || "redeem.html";
        a.textContent = "Redeem code";
        actions.appendChild(a);
      }

      card.appendChild(actions);
      listEl.appendChild(card);
    });
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function loadHistory() {
    loadingEl.hidden = false;
    errorEl.hidden = true;
    listEl.hidden = true;
    emptyEl.hidden = true;

    try {
      const res = await fetch(
        apiUrl("/api/purchases/history?token=" + encodeURIComponent(token))
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Could not load history");
      renderOrders(data);
    } catch (err) {
      loadingEl.hidden = true;
      errorEl.hidden = false;
      errorEl.textContent = err.message;
      requestSection.hidden = false;
    }
  }

  requestForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    requestMsg.hidden = true;
    requestErr.hidden = true;

    try {
      const res = await fetch(apiUrl("/api/purchases/request-access"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: emailInput.value.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Request failed");
      requestMsg.hidden = false;
      requestMsg.textContent = data.message || "Check your email for the link.";
    } catch (err) {
      requestErr.hidden = false;
      requestErr.textContent = err.message;
    }
  });

  if (token) {
    loadHistory();
  }
})();
