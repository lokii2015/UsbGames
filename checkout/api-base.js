/**
 * API + site URL for UsbGames (Render). Same-origin on Render/localhost.
 */
(function () {
  var CANONICAL = "https://usbgames.onrender.com";
  var host = (location.hostname || "").toLowerCase();

  if (host.endsWith(".netlify.app")) {
    location.replace(CANONICAL + location.pathname + location.search + location.hash);
    return;
  }

  var isLocal = host === "localhost" || host === "127.0.0.1";
  var isRender = host.endsWith(".onrender.com");

  var meta = document.querySelector('meta[name="usbgames-api"]');
  var fromMeta = meta && meta.getAttribute("content");
  var fromWin =
    typeof window.USBGAMES_API_BASE === "string" ? window.USBGAMES_API_BASE : "";

  var api = (fromWin || fromMeta || "").replace(/\/$/, "");
  if (!api && !isLocal && !isRender) {
    api = CANONICAL;
  }

  window.USBGAMES_API = api;
  window.USBGAMES_SITE_URL =
    isRender || isLocal ? location.origin.replace(/\/$/, "") : CANONICAL;
})();
