(function () {
  const form = document.getElementById("redeem-form");
  const errEl = document.getElementById("redeem-error");
  const loadEl = document.getElementById("redeem-loading");
  const box = document.getElementById("redeem-downloads");
  const list = document.getElementById("redeem-download-list");
  const namesEl = document.getElementById("redeem-product-names");
  const emailInput = document.getElementById("redeem-email");
  const codeInput = document.getElementById("redeem-code");

  const params = new URLSearchParams(location.search);
  if (params.get("email")) emailInput.value = params.get("email");
  if (params.get("code")) codeInput.value = params.get("code");

  function apiUrl(path) {
    const base = typeof window.USBGAMES_API === "string" ? window.USBGAMES_API : "";
    return base + path;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errEl.hidden = true;
    box.hidden = true;
    list.innerHTML = "";
    loadEl.hidden = false;

    let data = {};
    try {
      const res = await fetch(apiUrl("/api/redeem"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: emailInput.value.trim(),
          code: codeInput.value.trim(),
        }),
      });
      data = await res.json();
      if (!res.ok) throw new Error(data.error || data.message || "Redeem failed");

      const names = (data.products || [data.product]).map((p) => p.name).join(", ");
      namesEl.textContent = names;
      const base = typeof window.USBGAMES_API === "string" ? window.USBGAMES_API : "";
      data.downloads.forEach((d) => {
        const li = document.createElement("li");
        const a = document.createElement("a");
        a.className = "button";
        a.href = base + d.url;
        a.download = d.filename;
        a.textContent = "Download " + d.name;
        li.appendChild(a);
        list.appendChild(li);
      });
      box.hidden = false;
      try {
        localStorage.removeItem("usbgames_cart_v1");
      } catch (_) {}
    } catch (err) {
      errEl.hidden = false;
      let msg = err.message;
      if (data.expired || /expired/i.test(msg) || /48 hours/i.test(msg)) {
        const email = data.supportEmail || "EthanCiuffreda12@gmail.com";
        msg =
          (data.error || msg) +
          ' See <a href="refund.html">Refund Policy</a> and email <a href="mailto:' +
          email +
          '">' +
          email +
          "</a> with your PayPal receipt.";
        errEl.innerHTML = msg;
        return;
      }
      errEl.textContent = msg;
    } finally {
      loadEl.hidden = true;
    }
  });
})();
