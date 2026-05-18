/**
 * Store buy buttons — open checkout page (PayPal / card / paypal.me).
 */
(function () {
  const buttons = document.querySelectorAll("[data-checkout-product]");

  buttons.forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const productId = btn.getAttribute("data-checkout-product");
      if (productId) {
        window.location.href =
          "/checkout.html?product=" + encodeURIComponent(productId);
      }
    });
  });
})();
