/**
 * API base URL for static hosting (Netlify). Leave empty when /api is proxied to Render.
 * Optional: <meta name="usbgames-api" content="https://your-api.onrender.com" />
 */
(function () {
  var meta = document.querySelector('meta[name="usbgames-api"]');
  var fromMeta = meta && meta.getAttribute("content");
  var fromWin =
    typeof window.USBGAMES_API_BASE === "string" ? window.USBGAMES_API_BASE : "";
  window.USBGAMES_API = (fromWin || fromMeta || "").replace(/\/$/, "");
})();
