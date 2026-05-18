/**
 * Store page — Add to cart + Buy now
 */
(function () {
  const catalog = window.UsbGamesCatalog;
  const cart = window.UsbGamesCart;
  if (!catalog || !cart) return;

  function toast(msg) {
    let el = document.getElementById("cart-toast");
    if (!el) {
      el = document.createElement("p");
      el.id = "cart-toast";
      el.className = "cart-toast";
      el.setAttribute("role", "status");
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.classList.add("cart-toast--show");
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove("cart-toast--show"), 2200);
  }

  document.querySelectorAll("[data-checkout-product]").forEach((btn) => {
    const productId = btn.getAttribute("data-checkout-product");
    if (!productId) return;

    const product = catalog.getProduct(productId);
    if (!product) return;

    const row = btn.closest(".card, .store-featured-body, article");
    if (row && !row.querySelector(".store-cart-actions")) {
      const wrap = document.createElement("div");
      wrap.className = "store-cart-actions";
      btn.parentNode.insertBefore(wrap, btn);
      wrap.appendChild(btn);

      const addBtn = document.createElement("button");
      addBtn.type = "button";
      addBtn.className = "button small button--secondary";
      addBtn.textContent = "Add to cart";
      addBtn.setAttribute("data-add-to-cart", productId);
      wrap.insertBefore(addBtn, btn);

      btn.textContent = btn.textContent.replace(/^Buy/, "Buy now") || "Buy now — " + product.priceLabel;
    }

    btn.addEventListener("click", (e) => {
      e.preventDefault();
      cart.add(productId);
      location.href = "checkout.html";
    });
  });

  document.querySelectorAll("[data-add-to-cart]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const id = btn.getAttribute("data-add-to-cart");
      if (cart.add(id)) {
        const p = catalog.getProduct(id);
        toast(p ? "Added " + p.name + " to cart" : "Added to cart");
        btn.textContent = "Added ✓";
        setTimeout(() => {
          btn.textContent = "Add to cart";
        }, 1500);
      }
    });
  });

  cart.syncFromUrl();
})();
