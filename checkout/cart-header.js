/** Cart badge in site header — include after catalog.js + cart.js */
(function () {
  function updateBadge() {
    const n = window.UsbGamesCart?.count() || 0;
    document.querySelectorAll("[data-cart-count]").forEach((el) => {
      el.textContent = String(n);
      el.hidden = n === 0;
    });
    document.querySelectorAll("[data-cart-link]").forEach((el) => {
      el.setAttribute("aria-label", n ? `Cart, ${n} items` : "Cart, empty");
    });
  }

  if (window.UsbGamesCart) {
    window.UsbGamesCart.onChange(updateBadge);
    updateBadge();
  }
})();
